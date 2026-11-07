import httpx

from app.models import Ingest
from app.security import sender_hash
from tests.conftest import intake


async def test_public_simulation_cannot_edit_live_telegram_message(desk):
    app, client = desk
    await app.state.pipeline.ingest(
        Ingest(
            text="Need insulin Velachery",
            chat_id="-123",
            tg_message_id=1,
            sender_id="456",
            simulated=False,
        )
    )
    await app.state.pipeline.queue.join()
    response = await client.post(
        "/api/ingest",
        json={
            "text": "I have boat in Manali",
            "chat_id": "-123",
            "tg_message_id": 1,
            "sender_id": "456",
            "edited": True,
            "simulated": True,
        },
    )
    assert response.status_code == 200
    await app.state.pipeline.queue.join()
    row = await app.state.db.one("SELECT * FROM messages WHERE chat_id='-123' AND tg_message_id=1")
    assert row["text_raw"] == "Need insulin Velachery" and row["simulated"] == 0
    assert (await app.state.db.one("SELECT COUNT(*) n FROM cards"))["n"] == 2


async def test_live_match_requires_login_even_when_demo_is_open(desk):
    app, client = desk
    for text, sender in [("Need insulin Velachery", "1"), ("Have insulin Velachery", "2")]:
        await app.state.pipeline.ingest(Ingest(text=text, sender_id=sender, simulated=False))
    await app.state.pipeline.queue.join()
    assert (await client.post("/api/matches/1/approve", json={})).status_code == 401
    assert (
        await client.post(
            "/api/matches/1/approve", headers={"Authorization": "Bearer " + "c" * 32}, json={}
        )
    ).status_code == 200
    await app.state.db.forget(sender_hash("1", app.state.settings.salt))
    survivor = await app.state.db.one("SELECT * FROM cards")
    assert survivor["status"] == "open"


async def test_non_ascii_login_fails_cleanly(desk):
    _, client = desk
    assert (await client.post("/api/login", json={"token": "குறியீடு"})).status_code == 401


async def test_missing_api_route_has_consistent_error_shape(desk):
    _, client = desk
    response = await client.get("/api/unknown/path")
    assert response.status_code == 404
    assert set(response.json()) == {"error", "detail"}


async def test_llm_missing_fields_is_retried_and_falls_back(desk, respx_mock):
    app, client = desk
    s = app.state.settings
    s.llm_base_url = "https://llm.invalid"
    s.llm_api_key = "test"
    s.llm_model = "test"
    route = respx_mock.post("https://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )
    await intake(app, client, "Need insulin Velachery")
    card = await app.state.db.one("SELECT * FROM cards")
    assert route.call_count == 2 and card["extractor"] == "fallback"


async def test_global_urgency_before_page_limit(desk):
    app, client = desk
    for i in range(3):
        await intake(app, client, "Need blanket Manali", str(i))
    await intake(app, client, "Need insulin Velachery", "critical")
    rows = (await client.get("/api/cards?limit=1")).json()["items"]
    assert rows[0]["urgency"] == 5
