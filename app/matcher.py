import json
from datetime import UTC, datetime, timedelta

from rapidfuzz.fuzz import ratio

from app.config import Settings
from app.db import Database, now
from app.fallback_extractor import SYNONYMS
from app.geo import approximate_area, haversine
from app.security import redact


def canonical(text: str) -> str:
    lower = text.casefold().strip()
    for key, (_, aliases) in SYNONYMS.items():
        if lower == key or lower in aliases:
            return key
    return lower


def item_similarity(first: str, second: str) -> float:
    return ratio(canonical(first), canonical(second)) / 100


def match_score(need: dict, offer: dict, radius: float) -> tuple[float, float, dict]:
    distance = haversine(need["lat"], need["lng"], offer["lat"], offer["lng"])
    oldest = min(
        datetime.fromisoformat(need["created_at"]), datetime.fromisoformat(offer["created_at"])
    )
    recency = max(0, 1 - (datetime.now(UTC) - oldest).total_seconds() / 43200)
    parts = {
        "item": item_similarity(need["item_en"], offer["item_en"]),
        "distance": max(0, 1 - distance / radius),
        "urgency": need["urgency"] / 5,
        "recency": recency,
    }
    return (
        sum(parts[key] * weight for key, weight in zip(parts, (0.45, 0.25, 0.2, 0.1), strict=True)),
        distance,
        parts,
    )


async def suggest(db: Database, card: dict, settings: Settings) -> list[int]:
    if card["status"] != "open" or card["possible_misinformation"] or card["lat"] is None:
        return []
    cutoff = (datetime.now(UTC) - timedelta(hours=12)).isoformat()
    rows = await db.all(
        "SELECT * FROM cards WHERE intent!=? AND category=? AND status='open' AND possible_misinformation=0 AND lat IS NOT NULL AND simulated=? AND created_at>=? AND sender_hash!=?",
        (card["intent"], card["category"], card["simulated"], cutoff, card["sender_hash"]),
    )
    candidates = []
    for other in rows:
        need, offer = (card, other) if card["intent"] == "need" else (other, card)
        score, distance, breakdown = match_score(need, offer, settings.match_radius_km)
        if (
            distance <= settings.match_radius_km
            and score >= settings.match_min_score
            and breakdown["item"] >= 0.8
        ):
            candidates.append((score, need, offer, distance, breakdown))
    ids = []
    for score, need, offer, distance, breakdown in sorted(
        candidates, key=lambda c: c[0], reverse=True
    )[:3]:
        existing = await db.one(
            "SELECT id FROM matches WHERE need_id=? AND offer_id=?", (need["id"], offer["id"])
        )
        if existing:
            continue
        mid = await db.execute(
            "INSERT INTO matches(need_id,offer_id,distance_km,score,breakdown,status,created_at) VALUES(?,?,?,?,?,'suggested',?)",
            (need["id"], offer["id"], distance, score, json.dumps(breakdown), now()),
        )
        await db.audit("suggested", "match", mid)
        ids.append(mid)
    return ids


def notification(need: dict, offer: dict, distance: float) -> str:
    area = approximate_area(need["lat"], need["lng"])
    rounded = round(distance * 2) / 2
    prefix = "[SIMULATED] " if need["simulated"] else ""
    text = f"{prefix}Coordinator-approved suggestion: {redact(need['item_en'])}, {area}, approximately {rounded:.1f} km. Please message each other to verify availability and arrange help. Not an emergency service."
    translations = {
        "ta": "ஒருங்கிணைப்பாளர் ஒப்புதல் அளித்துள்ளார். உதவியை உறுதிசெய்ய இருவரும் தனியாகத் தொடர்புகொள்ளவும். இது அவசர சேவை அல்ல.",
        "es": "Sugerencia aprobada. Contactad en privado para verificar la ayuda. No es un servicio de emergencias.",
        "de": "Vorschlag genehmigt. Bitte die Hilfe privat bestätigen. Kein Notfalldienst.",
    }
    return text + (
        "\n" + translations[need["language"]] if need["language"] in translations else ""
    )
