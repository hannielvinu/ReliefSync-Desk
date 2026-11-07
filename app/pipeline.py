import asyncio
import json
import logging
import re
import secrets

from app.config import Settings
from app.db import Database, now
from app.events import EventBroker
from app.extractor import Extractor
from app.geo import Geocoder
from app.matcher import suggest
from app.models import Ingest
from app.security import RateLimiter, redact, sender_hash
from app.triage import invalidate_matches, triage

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, db: Database, settings: Settings, extractor: Extractor, geo: Geocoder, events: EventBroker):
        self.db, self.settings, self.extractor, self.geo, self.events = db, settings, extractor, geo, events
        self.queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1000)
        self.tasks: list[asyncio.Task] = []
        self.limiter = RateLimiter(30, 0.5)
        self.telegram = None
        self.edit_lock = asyncio.Lock()

    async def start(self) -> None:
        self.tasks = [asyncio.create_task(self.worker()) for _ in range(self.settings.llm_concurrency)]
        rows = await self.db.all("SELECT id FROM messages WHERE processing_state='queued'")
        for row in rows:
            await self.queue.put(row["id"])

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def ingest(self, data: Ingest) -> tuple[int, bool]:
        sender = sender_hash(data.sender_id, self.settings.salt)
        if not self.limiter.allow(sender):
            raise ValueError("Sender rate limit exceeded")
        message_id = data.tg_message_id if data.tg_message_id is not None else secrets.randbits(52)
        async with self.db.transaction():
            old = await self.db.one("SELECT * FROM messages WHERE chat_id=? AND tg_message_id=?", (data.chat_id, message_id))
            if old and not data.edited:
                return old["id"], False
            if old and old["sender_hash"] != sender:
                raise ValueError("Sender mismatch for edited message")
            if self.queue.full():
                raise ValueError("Intake queue full; retry later")
            if old:
                mid = old["id"]
                await self.db.execute("UPDATE messages SET text_raw=?,text_redacted=?,processing_state='queued',pin_lat=?,pin_lng=? WHERE id=?", (data.text, redact(data.text), data.lat, data.lng, mid))
            else:
                mid = await self.db.execute("INSERT INTO messages(chat_id,tg_message_id,sender_hash,sender_display,sender_id,text_raw,text_redacted,received_at,simulated,pin_lat,pin_lng) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (data.chat_id, message_id, sender, data.sender_display, data.sender_id if not data.simulated else None, data.text, redact(data.text), now(), int(data.simulated), data.lat, data.lng))
                await self.db.execute("INSERT OR IGNORE INTO participants(sender_hash,first_seen,simulated) VALUES(?,?,?)", (sender, now(), int(data.simulated)))
        await self.queue.put(mid)
        return mid, True

    async def worker(self) -> None:
        while True:
            mid = await self.queue.get()
            try:
                await self.process(mid)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("pipeline_failed message_id=%s", mid)
                async with self.db.transaction():
                    await self.db.execute("UPDATE messages SET processing_state='failed',reason='Extraction or processing unavailable' WHERE id=?", (mid,))
            finally:
                self.queue.task_done()

    async def process(self, mid: int) -> None:
        # Per-message reread below prevents stale edits from winning a concurrent extraction.
        msg = await self.db.one("SELECT * FROM messages WHERE id=?", (mid,))
        if not msg:
            return
        text = msg["text_raw"]
        ignored = len(text.strip()) < 3 or not any(c.isalnum() for c in text) or bool(re.fullmatch(r"https?://\S+", text.strip()))
        if ignored:
            result, mode = None, "fallback"
        else:
            result, mode = await self.extractor.extract(text)
        location = await self.geo.resolve(result.location_text, msg["pin_lat"], msg["pin_lng"]) if result else (None, None, "none", 0.0)
        async with self.db.transaction():
            current = await self.db.one("SELECT * FROM messages WHERE id=?", (mid,))
            if not current or current["text_raw"] != text:
                return
            old = await self.db.one("SELECT * FROM cards WHERE message_id=?", (mid,))
            if old:
                await invalidate_matches(self.db, old["id"], "Source message edited")
                if old["duplicate_of"]:
                    await self.db.execute("UPDATE cards SET repeat_count=MAX(1,repeat_count-1) WHERE id=?", (old["duplicate_of"],))
            if not result or (not result.is_actionable and not result.possible_misinformation) or result.intent not in {"need", "offer", "info"}:
                await self.db.execute("UPDATE messages SET processing_state='ignored',reason='Non-actionable or prefiltered' WHERE id=?", (mid,))
                if old:
                    await self.db.execute("UPDATE cards SET status='rejected',updated_at=? WHERE id=?", (now(), old["id"]))
            else:
                lat, lng, source, confidence = location
                fields = {"message_id": mid, "sender_hash": msg["sender_hash"], "intent": result.intent, "category": result.category, "item": result.item, "item_en": result.item_en, "quantity": result.quantity, "location_text": result.location_text, "lat": lat, "lng": lng, "loc_source": source, "loc_confidence": confidence, "urgency": result.urgency, "urgency_reason": result.urgency_reason, "vulnerable_flags": json.dumps(result.vulnerable_flags), "language": result.language, "message_en": result.message_en, "confidence": result.confidence, "extractor": mode, "status": "needs_location" if lat is None else "open", "possible_misinformation": int(result.possible_misinformation), "simulated": msg["simulated"], "updated_at": now()}
                if old:
                    await self.db.execute("UPDATE cards SET " + ",".join(f"{k}=?" for k in fields) + ",duplicate_of=NULL WHERE id=?", (*fields.values(), old["id"]))
                    cid = old["id"]
                else:
                    fields["created_at"] = now()
                    cid = await self.db.execute(f"INSERT INTO cards({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", tuple(fields.values()))
                card = await self.db.one("SELECT * FROM cards WHERE id=?", (cid,))
                if not card["possible_misinformation"]:
                    await triage(self.db, card, self.settings)
                card = await self.db.one("SELECT * FROM cards WHERE id=?", (cid,))
                matches = await suggest(self.db, card, self.settings)
                await self.db.execute("UPDATE messages SET processing_state='processed',language=? WHERE id=?", (result.language, mid))
                await self.db.audit("updated" if old else "created", "card", cid, {"extractor": mode})
                self.events.publish("card_updated" if old else "card_created", {"id": cid})
                for match_id in matches:
                    self.events.publish("match_suggested", {"id": match_id})
        if result and result.is_actionable and not old and not msg["simulated"] and self.telegram:
            await self.telegram.ack(msg, result, location[0] is None)
        self.events.publish("stats")
