import asyncio
import time

import httpx
import pytest

from app.config import Settings
from app.geo import approximate_area, haversine, local_place
from app.security import (
    RateLimiter,
    fuzz,
    public_card,
    redact,
    sender_hash,
    sign_session,
    valid_session,
)


@pytest.mark.parametrize(
    "text",
    ["+91 99999 11111", "reach test@example.invalid", "number 1234567890", "12 Example Street"],
)
def test_redacts_contacts(text):
    assert redact(text) != text
    assert "hidden]" in redact(text)


def test_hash_and_signed_sessions():
    assert sender_hash("12", "a") == sender_hash("12", "a")
    assert sender_hash("12", "b") != sender_hash("12", "a")
    token = sign_session("a")
    assert valid_session(token, "a")
    assert not valid_session(token, "b")
    assert not valid_session("bad", "a")
    assert not valid_session("1.x.bad", "a")


@pytest.mark.parametrize(
    "lat,lng", [(12.9756, 80.2207), (39.4287, -0.4181), (0, 0), (-12.1, -179.9)]
)
def test_fuzz_never_exact_and_deterministic(lat, lng):
    result = fuzz(lat, lng, 1, "salt")
    assert result != (lat, lng)
    assert result == fuzz(lat, lng, 1, "salt")
    assert abs(result[0] - lat) < 0.005
    assert abs(result[1] - lng) < 0.005
    assert result != fuzz(lat, lng, 2, "salt")


def test_public_card_excludes_identifiers():
    card = {
        "id": 1,
        "lat": 12.9756,
        "lng": 80.2207,
        "sender_hash": "private",
        "message_id": 3,
        "location_text": "12 Example Street",
        "item": "call 9999999999",
    }
    result = public_card(card, Settings(_env_file=None))
    assert "sender_hash" not in result and "message_id" not in result
    assert "9999999999" not in result["item"]
    assert "Street" not in result["location_text"]


def test_geo_math_and_locality():
    assert haversine(0, 0, 0, 0) == 0
    assert haversine(0, 0, 0, 1) == pytest.approx(111.195, rel=0.001)
    assert haversine(0, 0, 0, 180) == pytest.approx(20015, rel=0.001)
    assert local_place("வேளச்சேரி")["name"] == "Velachery"
    assert local_place("Velacheri")["name"] == "Velachery"
    assert local_place("unknown qxyz") is None
    assert approximate_area(12.9756, 80.2207) == "Velachery area"
    assert approximate_area(0, 0) == "Approximate area"
    assert approximate_area(None, None) == "Location needed"


def test_rate_limit_refill_and_bound():
    limiter = RateLimiter(1, 100)
    assert limiter.allow("one")
    assert not limiter.allow("one")
    time.sleep(0.02)
    assert limiter.allow("one")
    for i in range(10002):
        limiter.allow(str(i))
    assert len(limiter.buckets) == 10000


def test_settings_production_and_webhook_validation():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production")
    with pytest.raises(ValueError):
        Settings(_env_file=None, telegram_mode="webhook")
    with pytest.raises(ValueError):
        Settings(_env_file=None, geocoder_url="https://geo.invalid")
    assert Settings(_env_file=None, app_env="production", salt="s" * 32, coordinator_token="c" * 24)


async def test_geocoder_order_cache_limiter_and_failure(desk, respx_mock):
    app, _ = desk
    geo = app.state.geo
    assert await geo.resolve("Velachery", 1, 2) == (1, 2, "pin", 1)
    assert (await geo.resolve("Velachery"))[2] == "gazetteer"
    assert (await geo.resolve(""))[2] == "none"
    assert (await geo.resolve("unknown qxyz"))[2] == "none"
    geo.settings.geocoder_url = "https://geo.invalid/search"
    route = respx_mock.get("https://geo.invalid/search").mock(
        return_value=httpx.Response(
            200, json=[{"lat": "1.2", "lon": "3.4", "display_name": "Test place"}]
        )
    )
    assert (await geo.resolve("Test unknown qxyz"))[2] == "nominatim"
    assert (await geo.resolve("Test unknown qxyz"))[0] == 1.2
    assert route.call_count == 1
    assert (await geo.resolve("phone 9999999999"))[2] == "none"
    route.mock(return_value=httpx.Response(503))
    start = time.monotonic()
    assert (await geo.resolve("Another unknown qxyz"))[2] == "none"
    assert time.monotonic() - start >= 0.8
    await asyncio.sleep(0)
