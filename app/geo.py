import asyncio
import json
import math
import time
from pathlib import Path

import httpx
from rapidfuzz import fuzz as rfuzz

from app.config import Settings
from app.db import Database, now
from app.security import redact

GAZETTEER = json.loads(
    (Path(__file__).resolve().parents[1] / "data/gazetteer.json").read_text(encoding="utf-8")
)


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlng = b - a, math.radians(lng2 - lng1)
    value = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


def local_place(text: str) -> dict | None:
    lower = text.casefold()
    best, best_score = None, 0.0
    for place in GAZETTEER:
        for alias in place["aliases"]:
            score = 100 if alias.casefold() in lower else rfuzz.WRatio(lower, alias.casefold())
            if score > best_score:
                best, best_score = place, score
    return best if best_score >= 85 else None


def approximate_area(lat: float | None, lng: float | None) -> str:
    if lat is None or lng is None:
        return "Location needed"
    closest = min(GAZETTEER, key=lambda p: haversine(lat, lng, p["lat"], p["lng"]))
    if haversine(lat, lng, closest["lat"], closest["lng"]) <= 5:
        return closest["name"] + " area"
    return "Approximate area"


class Geocoder:
    def __init__(self, db: Database, settings: Settings, client: httpx.AsyncClient):
        self.db, self.settings, self.client = db, settings, client
        self.lock = asyncio.Lock()
        self.last_request = 0.0

    async def resolve(
        self, text: str, lat: float | None = None, lng: float | None = None
    ) -> tuple[float | None, float | None, str, float]:
        if lat is not None and lng is not None:
            return lat, lng, "pin", 1.0
        if not text.strip():
            return None, None, "none", 0.0
        place = local_place(text)
        if place:
            return place["lat"], place["lng"], "gazetteer", 0.8
        query = redact(text).strip().casefold()
        if "[" in query or not self.settings.geocoder_url:
            return None, None, "none", 0.0
        async with self.lock:
            cached = await self.db.one("SELECT * FROM geocache WHERE query=?", (query,))
            if cached:
                return cached["lat"], cached["lng"], "nominatim", 0.6
            await asyncio.sleep(max(0, 1.05 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = await self.client.get(
                    self.settings.geocoder_url,
                    params={"q": query, "format": "json", "limit": 1},
                    headers={"User-Agent": self.settings.geocoder_user_agent},
                    timeout=8,
                )
                response.raise_for_status()
                results = response.json()
                if results:
                    row = results[0]
                    lat, lng = float(row["lat"]), float(row["lon"])
                    async with self.db.transaction():
                        await self.db.execute(
                            "INSERT OR REPLACE INTO geocache VALUES(?,?,?,?,?)",
                            (query, lat, lng, row.get("display_name", ""), now()),
                        )
                    return lat, lng, "nominatim", 0.6
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        return None, None, "none", 0.0
