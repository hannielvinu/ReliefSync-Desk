import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx

from app.config import Settings
from app.db import Database, now
from app.events import EventBroker
from app.i18n import acknowledgement
from app.matcher import notification
from app.models import Extraction, Ingest
from app.pipeline import Pipeline
from app.security import sender_hash
from app.triage import invalidate_matches

logger = logging.getLogger(__name__)
HELP = "ReliefSync Desk records text needs/offers for volunteer review. Share a location pin with the paperclip menu. Every match needs human approval. Not an emergency service: contact local emergency services first. /privacy /forget /iam <country> /status"


class Telegram:
    def __init__(self, settings: Settings, db: Database, client: httpx.AsyncClient, pipeline: Pipeline, events: EventBroker):
        self.settings, self.db, self.client, self.pipeline, self.events = settings, db, client, pipeline, events
        self.task: asyncio.Task | None = None
        self.status = "disabled"
        self.privacy_disabled = False
        self.chat_times: dict[str, float] = {}
        self.unsupported_times: dict[str, float] = {}
        self.send_lock = asyncio.Lock()

    async def call(self, method: str, payload: dict | None = None) -> object:
        response = await self.client.post(f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/{method}", json=payload or {}, timeout=40)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ValueError("Telegram request rejected")
        return data["result"]

    async def start(self) -> None:
        if not self.settings.telegram_bot_token:
            return
        try:
            info = await self.call("getMe")
            self.privacy_disabled = bool(info.get("can_read_all_group_messages"))
            self.settings.telegram_bot_username = info["username"]
            if self.settings.telegram_mode == "polling":
                await self.call("deleteWebhook", {"drop_pending_updates": False})
                self.task = asyncio.create_task(self.poll())
            else:
                await self.call("setWebhook", {"url": self.settings.public_base_url.rstrip("/") + "/telegram/webhook/" + self.settings.telegram_webhook_secret, "secret_token": self.settings.telegram_webhook_secret, "allowed_updates": ["message", "edited_message"]})
            self.status = self.settings.telegram_mode
        except (httpx.HTTPError, ValueError, KeyError):
            self.status = "error"
            logger.error("telegram_start_failed")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def poll(self) -> None:
        stored = await self.db.one("SELECT value FROM runtime WHERE key='telegram_offset'")
        offset = int(stored["value"]) if stored else 0
        while True:
            try:
                updates = await self.call("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "edited_message"]})
                for update in updates:
                    await self.handle(update)
                    offset = update["update_id"] + 1
                    async with self.db.transaction():
                        await self.db.execute("INSERT OR REPLACE INTO runtime VALUES('telegram_offset',?)", (str(offset),))
                self.status = "polling"
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, ValueError, KeyError):
                self.status = "reconnecting"
                await asyncio.sleep(3)

    async def send(self, chat_id: str, text: str, entities: list | None = None) -> None:
        async with self.send_lock:
            await asyncio.sleep(max(0, 2 - (time.monotonic() - self.chat_times.get(chat_id, 0))))
            await self.call("sendMessage", {"chat_id": chat_id, "text": text, "entities": entities or [], "link_preview_options": {"is_disabled": True}})
            self.chat_times[chat_id] = time.monotonic()
            if len(self.chat_times) > 5000:
                self.chat_times.pop(next(iter(self.chat_times)))

    async def ack(self, msg: dict, result: Extraction, missing: bool) -> None:
        if self.settings.telegram_ack_mode == "off":
            return
        # Use trusted templates rather than potentially contact-bearing provider output.
        text = acknowledgement(result.language, missing) + f" Logged: {result.intent.upper()}, urgency {result.urgency}."
        try:
            await self.send(msg["chat_id"], text)
        except (httpx.HTTPError, ValueError):
            logger.warning("telegram_ack_failed message_id=%s", msg["id"])

    async def handle(self, update: dict) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message or message.get("from", {}).get("is_bot"):
            return
        chat = str(message["chat"]["id"])
        sender_id = str(message["from"]["id"])
        sender = sender_hash(sender_id, self.settings.salt)
        text = message.get("text", "")[:1000]
        if text.startswith("/"):
            command, _, argument = text.partition(" ")
            command = command.split("@")[0]
            if command == "/forget":
                await self.pipeline.queue.join()
                await self.db.forget(sender)
                self.events.publish("card_updated")
                reply = "Your stored messages, cards and participation record were deleted. Related matches were rejected. Telegram copies cannot be erased by this app."
            elif command == "/privacy":
                reply = "We store your text and Telegram routing IDs privately. Public views hide contacts and approximate locations. Configured extraction/geocoding providers may process text. /forget erases your app records."
            elif command == "/iam":
                country = argument.strip()[:60]
                if not country or not all(c.isalpha() or c in " -'" for c in country):
                    reply = "Use /iam <country>, for example /iam India. Optional and self-reported."
                else:
                    async with self.db.transaction():
                        await self.db.execute("INSERT INTO participants(sender_hash,first_seen,country,simulated) VALUES(?,?,?,0) ON CONFLICT(sender_hash) DO UPDATE SET country=excluded.country", (sender, now(), country.title()))
                    reply = "Optional self-reported country recorded."
            elif command == "/status":
                count = await self.db.one("SELECT COUNT(*) AS n FROM cards WHERE sender_hash=? AND status IN ('open','needs_location','matched')", (sender,))
                reply = f"Your active cards: {count['n']}."
            else:
                reply = HELP
            if command in {"/start", "/status", "/help"} and not self.privacy_disabled:
                reply += " Group intake may be limited: disable privacy using BotFather /setprivacy, or make the bot a group admin."
            await self.send(chat, reply)
            self.events.publish("stats")
            return
        if "location" in message:
            await self.pipeline.queue.join()
            cutoff = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
            async with self.db.transaction():
                row = await self.db.one("SELECT c.id,c.message_id FROM cards c JOIN messages m ON m.id=c.message_id WHERE c.sender_hash=? AND m.chat_id=? AND c.lat IS NULL AND c.created_at>=? AND c.status='needs_location' ORDER BY c.id DESC LIMIT 1", (sender, chat, cutoff))
                if row:
                    await invalidate_matches(self.db, row["id"], "Location updated")
                    await self.db.execute("UPDATE messages SET pin_lat=?,pin_lng=?,processing_state='queued' WHERE id=?", (message["location"]["latitude"], message["location"]["longitude"], row["message_id"]))
            if row:
                await self.pipeline.queue.put(row["message_id"])
            else:
                await self.send(chat, "Please send a text need or offer before sharing its location (within 15 minutes).")
            return
        if not text:
            if time.monotonic() - self.unsupported_times.get(chat, -3600) > 3600:
                self.unsupported_times[chat] = time.monotonic()
                await self.send(chat, "Text and location pins only for now. Not an emergency service.")
            return
        await self.pipeline.ingest(Ingest(text=text, chat_id=chat, tg_message_id=message["message_id"], sender_id=sender_id, simulated=False, edited="edited_message" in update))

    async def notify_match(self, match: dict, need: dict, offer: dict) -> str:
        if need["simulated"] or not self.settings.telegram_bot_token:
            return "would_send"
        source = await self.db.one("SELECT * FROM messages WHERE id=?", (need["message_id"],))
        other = await self.db.one("SELECT * FROM messages WHERE id=?", (offer["message_id"],))
        text = notification(need, offer, match["distance_km"])
        entities = []
        for label, message in (("Requester", source), ("Volunteer", other)):
            offset = len(text.encode("utf-16-le")) // 2 + 1
            text += "\n" + label
            if message["sender_id"] and message["sender_id"].lstrip("-").isdigit():
                entities.append({"type": "text_mention", "offset": offset, "length": len(label), "user": {"id": int(message["sender_id"]), "is_bot": False, "first_name": label}})
        try:
            await self.send(source["chat_id"], text, entities)
            return "sent"
        except (httpx.HTTPError, ValueError):
            return "failed"
