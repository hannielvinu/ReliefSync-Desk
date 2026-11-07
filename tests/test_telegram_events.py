import asyncio
import json

import httpx

from app.events import EventBroker
from app.models import Ingest
from app.security import sender_hash


def update(text=None, sender=1, mid=1, **extra):
    return {
        "update_id": mid,
        "message": {
            "message_id": mid,
            "chat": {"id": -1},
            "from": {"id": sender},
            **({"text": text} if text is not None else {}),
            **extra,
        },
    }


async def test_telegram_text_edits_pin_and_commands(desk, respx_mock):
    app, _ = desk
    bot = app.state.telegram
    route = respx_mock.post("https://api.telegram.org/bot/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    # Prevent acknowledgement delays in command-heavy tests while still exercising the client.
    original_send = bot.send

    async def fast_send(chat, text, entities=None):
        bot.chat_times.clear()
        await original_send(chat, text, entities)

    bot.send = fast_send
    await bot.handle(update("Need insulin", mid=1))
    await app.state.pipeline.queue.join()
    card = await app.state.db.one("SELECT * FROM cards")
    assert card["status"] == "needs_location"
    await bot.handle(update(mid=2, location={"latitude": 12.9756, "longitude": 80.2207}))
    await app.state.pipeline.queue.join()
    assert (await app.state.db.one("SELECT * FROM cards"))["loc_source"] == "pin"
    edited = update("Need boat Velachery", mid=1)
    edited["edited_message"] = edited.pop("message")
    await bot.handle(edited)
    await app.state.pipeline.queue.join()
    assert (await app.state.db.one("SELECT * FROM cards"))["item_en"] == "boat"
    for command in ("/start", "/help", "/privacy", "/status", "/iam India", "/iam 123", "/unknown"):
        await bot.handle(update(command, mid=3))
    bodies = [json.loads(call.request.content) for call in route.calls]
    assert any("privacy" in b["text"].lower() and "BotFather" in b["text"] for b in bodies)
    assert (await app.state.db.one("SELECT * FROM participants"))["country"] == "India"
    await bot.handle(update(mid=4, photo=[{}]))
    sent = route.call_count
    await bot.handle(update(mid=5, sticker={}))
    assert route.call_count == sent
    await bot.handle(update("/forget", mid=6))
    assert not await app.state.db.all("SELECT * FROM cards")
    assert not await app.state.db.all("SELECT * FROM messages")
    assert not await app.state.db.all("SELECT * FROM participants")
    await bot.handle(update(mid=7, location={"latitude": 1, "longitude": 2}))
    await bot.handle({})
    await bot.handle(update("hello", mid=8, **{"from": {"id": 5, "is_bot": True}}))


async def test_forget_rejects_matches(desk):
    app, _ = desk
    for text, sender in [("Need insulin Velachery", "1"), ("Have insulin Velachery", "2")]:
        await app.state.pipeline.ingest(Ingest(text=text, sender_id=sender, simulated=False))
    await app.state.pipeline.queue.join()
    await app.state.db.forget(sender_hash("1", app.state.settings.salt))
    match = await app.state.db.one("SELECT * FROM matches")
    assert match["status"] == "rejected" and match["need_id"] is None


async def test_telegram_start_poll_and_notification(desk, respx_mock):
    app, _ = desk
    bot = app.state.telegram
    bot.settings.telegram_bot_token = "fake"
    base = "https://api.telegram.org/botfake/"
    respx_mock.post(base + "getMe").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"username": "test_bot", "can_read_all_group_messages": True},
            },
        )
    )
    respx_mock.post(base + "deleteWebhook").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": True})
    )

    async def poll_response(request):
        await asyncio.sleep(0.02)
        return httpx.Response(200, json={"ok": True, "result": []})

    respx_mock.post(base + "getUpdates").mock(side_effect=poll_response)
    route = respx_mock.post(base + "sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    await bot.start()
    await asyncio.sleep(0.05)
    assert bot.status == "polling" and bot.privacy_disabled
    await bot.stop()
    bot.settings.telegram_ack_mode = "off"
    for text, sender in [("Need insulin Velachery", "1"), ("Have insulin Velachery", "2")]:
        await app.state.pipeline.ingest(
            Ingest(text=text, sender_id=sender, chat_id="-1", simulated=False)
        )
    await app.state.pipeline.queue.join()
    match = await app.state.db.one("SELECT * FROM matches")
    need = await app.state.db.one("SELECT * FROM cards WHERE id=?", (match["need_id"],))
    offer = await app.state.db.one("SELECT * FROM cards WHERE id=?", (match["offer_id"],))
    assert await bot.notify_match(match, need, offer) == "sent"
    payload = json.loads(route.calls[-1].request.content)
    assert len(payload["entities"]) == 2 and "80.2207" not in payload["text"]
    bot.chat_times.clear()
    route.mock(return_value=httpx.Response(500))
    assert await bot.notify_match(match, need, offer) == "failed"


async def test_webhook_auth_and_registration(desk, respx_mock):
    app, client = desk
    s = app.state.settings
    assert (await client.post("/telegram/webhook/bad", json={})).status_code == 403
    s.telegram_mode = "webhook"
    s.telegram_webhook_secret = "secret" * 5
    s.telegram_bot_token = "fake"
    respx_mock.post("https://api.telegram.org/botfake/getMe").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"username": "test"}})
    )
    route = respx_mock.post("https://api.telegram.org/botfake/setWebhook").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": True})
    )
    await app.state.telegram.start()
    assert route.called
    assert (
        await client.post(
            "/telegram/webhook/" + s.telegram_webhook_secret,
            headers={"X-Telegram-Bot-Api-Secret-Token": s.telegram_webhook_secret},
            json={},
        )
    ).status_code == 200


async def test_sse_delivery_bounded_and_cleanup():
    broker = EventBroker()
    stream = broker.stream()
    assert "connected" in await anext(stream)
    broker.publish("card_created", {"id": 1})
    assert '"id": 1' in await anext(stream)
    for i in range(105):
        broker.publish("stats", {"n": i})
    assert next(iter(broker.clients)).qsize() == 100
    await stream.aclose()
    assert not broker.clients
