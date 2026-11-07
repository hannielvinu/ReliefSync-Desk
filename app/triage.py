import json
from datetime import UTC, datetime, timedelta

from rapidfuzz.fuzz import ratio

from app.config import Settings
from app.db import Database, now
from app.geo import haversine


def priority(card: dict) -> float:
    minutes = max(0, (datetime.now(UTC) - datetime.fromisoformat(card["created_at"])).total_seconds() / 60)
    flags = card.get("vulnerable_flags", "[]")
    vulnerable = bool(json.loads(flags)) if isinstance(flags, str) else bool(flags)
    return card["urgency"] * 20 + min(card.get("repeat_count", 1) - 1, 5) * 3 + min(minutes / 10, 10) + (5 if vulnerable else 0)


async def triage(db: Database, card: dict, settings: Settings) -> None:
    cutoff = (datetime.now(UTC) - timedelta(minutes=settings.dedupe_window_min)).isoformat()
    candidates = await db.all("SELECT * FROM cards WHERE id<? AND intent=? AND category=? AND simulated=? AND created_at>=? AND status IN ('open','needs_location','matched')", (card["id"], card["intent"], card["category"], card["simulated"], cutoff))
    for other in candidates:
        if ratio(card["item_en"], other["item_en"]) < 80:
            continue
        both_missing = card["lat"] is None and other["lat"] is None
        distance = haversine(card["lat"], card["lng"], other["lat"], other["lng"]) if card["lat"] is not None and other["lat"] is not None else float("inf")
        if card["sender_hash"] == other["sender_hash"] and (both_missing or distance < 0.3):
            await db.execute("UPDATE cards SET status='duplicate',duplicate_of=?,updated_at=? WHERE id=?", (other["id"], now(), card["id"]))
            await db.execute("UPDATE cards SET repeat_count=repeat_count+1 WHERE id=?", (other["id"],))
            await db.audit("duplicate_merged", "card", card["id"], {"duplicate_of": other["id"]})
            return
        if card["sender_hash"] != other["sender_hash"] and distance < 0.15:
            cluster = other["cluster_id"] or other["id"]
            await db.execute("UPDATE cards SET cluster_id=? WHERE id IN (?,?)", (cluster, card["id"], other["id"]))


async def invalidate_matches(db: Database, card_id: int, reason: str) -> None:
    rows = await db.all("SELECT * FROM matches WHERE (need_id=? OR offer_id=?) AND status IN ('suggested','approved')", (card_id, card_id))
    for row in rows:
        await db.execute("UPDATE matches SET status='rejected',note=?,decided_at=? WHERE id=?", (reason, now(), row["id"]))
        for partner in (row["need_id"], row["offer_id"]):
            await db.execute("UPDATE cards SET status='open',updated_at=? WHERE id=? AND status='matched'", (now(), partner))
        await db.audit("match_invalidated", "match", row["id"], {"reason": reason})
