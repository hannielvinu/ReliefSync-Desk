import hashlib
import hmac
import math
import re
import secrets
import time
from collections import OrderedDict

from app.config import Settings

CONTACT = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")
ADDRESS = re.compile(r"\b\d{1,5}\s+[\w .'-]{1,50}\b(?:street|road|avenue|lane|st\b|rd\b)", re.I)


def redact(text: str) -> str:
    return ADDRESS.sub("[address hidden]", CONTACT.sub("[contact hidden]", text))


def sender_hash(sender: str, salt: str) -> str:
    return hmac.new(salt.encode(), sender.encode(), hashlib.sha256).hexdigest()


def fuzz(lat: float, lng: float, card_id: int, salt: str) -> tuple[float, float]:
    digest = hmac.new(salt.encode(), str(card_id).encode(), hashlib.sha256).digest()
    offsets = [0.15 + int.from_bytes(digest[i:i + 4], "big") / (2**32) * 0.7 for i in (0, 4)]
    result = tuple(round(math.floor(coord / 0.005) * 0.005 + offset * 0.005, 6) for coord, offset in zip((lat, lng), offsets, strict=True))
    if result == (lat, lng):
        return round(lat + 0.000001, 6), result[1]
    return result


def public_card(card: dict, settings: Settings, exact: bool = False) -> dict:
    result = {key: value for key, value in card.items() if key not in {"sender_hash", "message_id"}}
    for key in ("item", "item_en", "message_en", "location_text", "urgency_reason"):
        result[key] = redact(str(result.get(key) or ""))
    if not exact:
        if result.get("lat") is not None and result.get("lng") is not None:
            result["lat"], result["lng"] = fuzz(result["lat"], result["lng"], card["id"], settings.salt)
        result["location_text"] = result.get("public_area") or "Approximate area" if result.get("lat") is not None else "Location needed"
    return result


def sign_session(salt: str) -> str:
    payload = f"{int(time.time()) + 43200}.{secrets.token_hex(16)}"
    signature = hmac.new(salt.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def valid_session(token: str, salt: str) -> bool:
    try:
        expiry, nonce, signature = token.split(".")
        expected = hmac.new(salt.encode(), f"{expiry}.{nonce}".encode(), hashlib.sha256).hexdigest()
        return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


class RateLimiter:
    def __init__(self, capacity: float = 60, per_second: float = 1):
        self.capacity = capacity
        self.rate = per_second
        self.buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def allow(self, key: str) -> bool:
        current = time.monotonic()
        tokens, previous = self.buckets.pop(key, (self.capacity, current))
        tokens = min(self.capacity, tokens + (current - previous) * self.rate)
        allowed = tokens >= 1
        self.buckets[key] = (tokens - 1 if allowed else tokens, current)
        if len(self.buckets) > 10000:
            self.buckets.popitem(last=False)
        return allowed
