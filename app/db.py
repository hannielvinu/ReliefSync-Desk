import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite


def now() -> str:
    return datetime.now(UTC).isoformat()


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, chat_id TEXT NOT NULL, tg_message_id INTEGER NOT NULL,
 sender_hash TEXT NOT NULL, sender_display TEXT, sender_id TEXT,
 text_raw TEXT NOT NULL, text_redacted TEXT NOT NULL, language TEXT DEFAULT 'en',
 received_at TEXT NOT NULL, simulated INTEGER NOT NULL, processing_state TEXT DEFAULT 'queued',
 reason TEXT, pin_lat REAL, pin_lng REAL, UNIQUE(chat_id,tg_message_id));
CREATE TABLE IF NOT EXISTS cards (
 id INTEGER PRIMARY KEY, message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
 sender_hash TEXT NOT NULL, intent TEXT, category TEXT, item TEXT, item_en TEXT, quantity INTEGER,
 location_text TEXT, lat REAL, lng REAL, loc_source TEXT, loc_confidence REAL,
 urgency INTEGER CHECK(urgency BETWEEN 1 AND 5), urgency_reason TEXT,
 vulnerable_flags TEXT DEFAULT '[]', language TEXT, message_en TEXT, confidence REAL,
 extractor TEXT, status TEXT, duplicate_of INTEGER REFERENCES cards(id) ON DELETE SET NULL,
 repeat_count INTEGER DEFAULT 1, cluster_id INTEGER, possible_misinformation INTEGER DEFAULT 0,
 simulated INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 location_asked INTEGER DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS card_message ON cards(message_id);
CREATE INDEX IF NOT EXISTS card_status ON cards(status,urgency,created_at);
CREATE INDEX IF NOT EXISTS card_category ON cards(intent,category);
CREATE TABLE IF NOT EXISTS matches (
 id INTEGER PRIMARY KEY, need_id INTEGER REFERENCES cards(id) ON DELETE SET NULL,
 offer_id INTEGER REFERENCES cards(id) ON DELETE SET NULL, distance_km REAL, score REAL,
 breakdown TEXT DEFAULT '{}', status TEXT DEFAULT 'suggested', created_at TEXT,
 decided_at TEXT, decided_by TEXT, note TEXT DEFAULT '', notification_state TEXT DEFAULT 'pending',
 UNIQUE(need_id,offer_id));
CREATE INDEX IF NOT EXISTS match_status ON matches(status);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, action TEXT, entity TEXT, entity_id INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS participants (
 sender_hash TEXT PRIMARY KEY, first_seen TEXT, country TEXT, simulated INTEGER);
CREATE TABLE IF NOT EXISTS geocache (query TEXT PRIMARY KEY, lat REAL, lng REAL, display_name TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS runtime (key TEXT PRIMARY KEY, value TEXT);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection
        self.lock = asyncio.Lock()

    async def open(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        await self.conn.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["Database"]:
        async with self.lock:
            try:
                yield self
                await self.conn.commit()
            except BaseException:
                await self.conn.rollback()
                raise

    async def execute(self, sql: str, args: tuple = ()) -> int:
        cursor = await self.conn.execute(sql, args)
        return cursor.lastrowid or 0

    async def all(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        async with self.conn.execute(sql, args) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = await self.all(sql, args)
        return rows[0] if rows else None

    async def audit(
        self,
        action: str,
        entity: str,
        entity_id: int,
        detail: dict | None = None,
        actor: str = "system",
    ) -> None:
        await self.execute(
            "INSERT INTO audit_log(ts,actor,action,entity,entity_id,detail) VALUES(?,?,?,?,?,?)",
            (now(), actor, action, entity, entity_id, json.dumps(detail or {})),
        )

    async def forget(self, sender: str) -> None:
        async with self.transaction():
            await self.execute("UPDATE cards SET status='open',updated_at=? WHERE status='matched' AND sender_hash!=? AND id IN (SELECT need_id FROM matches WHERE status='approved' AND offer_id IN (SELECT id FROM cards WHERE sender_hash=?) UNION SELECT offer_id FROM matches WHERE status='approved' AND need_id IN (SELECT id FROM cards WHERE sender_hash=?))", (now(), sender, sender, sender))
            await self.execute(
                "UPDATE matches SET status='rejected',note='Participant erased',decided_at=? WHERE need_id IN (SELECT id FROM cards WHERE sender_hash=?) OR offer_id IN (SELECT id FROM cards WHERE sender_hash=?)",
                (now(), sender, sender),
            )
            await self.execute(
                "DELETE FROM audit_log WHERE entity='card' AND entity_id IN (SELECT id FROM cards WHERE sender_hash=?)",
                (sender,),
            )
            await self.execute("DELETE FROM cards WHERE sender_hash=?", (sender,))
            await self.execute("DELETE FROM messages WHERE sender_hash=?", (sender,))
            await self.execute("DELETE FROM participants WHERE sender_hash=?", (sender,))

    async def purge_simulated(self) -> None:
        async with self.transaction():
            await self.execute(
                "DELETE FROM matches WHERE need_id IN (SELECT id FROM cards WHERE simulated=1) OR offer_id IN (SELECT id FROM cards WHERE simulated=1)"
            )
            await self.execute(
                "DELETE FROM audit_log WHERE entity='card' AND entity_id IN (SELECT id FROM cards WHERE simulated=1)"
            )
            await self.execute("DELETE FROM cards WHERE simulated=1")
            await self.execute("DELETE FROM messages WHERE simulated=1")
            await self.execute("DELETE FROM participants WHERE simulated=1")
