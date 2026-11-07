import hmac
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from app import __version__
from app.db import now
from app.geo import approximate_area
from app.matcher import notification, suggest
from app.models import CardPatch, Decision, DrillStart, Ingest, Login, Page
from app.security import public_card, redact, sign_session, valid_session
from app.triage import invalidate_matches

router = APIRouter()


def authenticated(request: Request) -> bool:
    settings = request.app.state.settings
    bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
    return bool(
        settings.coordinator_token
        and hmac.compare_digest(bearer.encode(), settings.coordinator_token.encode())
    ) or valid_session(request.cookies.get("session", ""), settings.salt)


def coordinator(request: Request) -> None:
    if not authenticated(request):
        raise HTTPException(401, "Coordinator login required")


def demo_or_coordinator(request: Request) -> None:
    if not request.app.state.settings.demo_mode:
        coordinator(request)


def safe(card: dict, request: Request, exact: bool = False) -> dict:
    card["public_area"] = approximate_area(card["lat"], card["lng"])
    return public_card(card, request.app.state.settings, exact)


@router.get("/health")
async def health(request: Request) -> dict:
    state = request.app.state
    await state.db.one("SELECT 1")
    failed = await state.db.one("SELECT COUNT(*) n FROM messages WHERE processing_state='failed'")
    return {
        "status": "ok",
        "db": "ok",
        "extractor": "llm" if state.settings.llm_configured else "fallback",
        "circuit_open": state.extractor.open_until > time.monotonic(),
        "telegram": state.telegram.status,
        "queue_depth": state.pipeline.queue.qsize(),
        "failed_messages": failed["n"],
        "version": __version__,
    }


@router.get("/api/config")
async def config(request: Request) -> dict:
    s = request.app.state.settings
    return {
        "demo_mode": s.demo_mode,
        "bot_username": s.telegram_bot_username,
        "test_group_url": s.test_group_url,
        "feedback_url": s.feedback_url,
        "version": __version__,
        "authenticated": authenticated(request),
    }


@router.post("/api/login")
async def login(body: Login, request: Request, response: Response) -> dict:
    s = request.app.state.settings
    if not s.coordinator_token or not hmac.compare_digest(
        body.token.encode(), s.coordinator_token.encode()
    ):
        raise HTTPException(401, "Invalid coordinator token")
    response.set_cookie(
        "session",
        sign_session(s.salt),
        httponly=True,
        secure=s.public_base_url.startswith("https://"),
        samesite="lax",
        max_age=43200,
    )
    return {"ok": True}


@router.post("/api/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/api/cards", response_model=Page)
async def cards(
    request: Request,
    intent: str = "",
    category: str = "",
    status: str = "",
    min_urgency: int = Query(1, ge=1, le=5),
    q: str = Query("", max_length=100),
    lang: str = "",
    flagged: bool = False,
    limit: int = Query(100, ge=1, le=200),
    cursor: int = Query(0, ge=0),
    sort: str = "priority",
) -> dict:
    clauses, args = ["urgency>=?"], [min_urgency]
    for key, value in (
        ("intent", intent),
        ("category", category),
        ("status", status),
        ("language", lang),
    ):
        if value:
            clauses.append(f"{key}=?")
            args.append(value)
    if flagged:
        clauses.append("possible_misinformation=1")
    if q:
        clauses.append("(item LIKE ? OR item_en LIKE ? OR location_text LIKE ?)")
        args.extend(["%" + q + "%"] * 3)
    priority_sql = "urgency*20 + min(repeat_count-1,5)*3 + min(max((julianday('now')-julianday(created_at))*144,0),10) + CASE WHEN vulnerable_flags!='[]' THEN 5 ELSE 0 END"
    order = (
        "id DESC"
        if sort == "newest"
        else "urgency DESC,id DESC"
        if sort == "urgency"
        else f"({priority_sql}) DESC,id DESC"
    )
    rows = await request.app.state.db.all(
        "SELECT * FROM cards WHERE "
        + " AND ".join(clauses)
        + f" ORDER BY {order} LIMIT ? OFFSET ?",
        (*args, limit + 1, cursor),
    )
    next_cursor = cursor + limit if len(rows) > limit else None
    rows = rows[:limit]
    return {"items": [safe(row, request) for row in rows], "next_cursor": next_cursor}


@router.get("/api/cards/{card_id}")
async def card_detail(card_id: int, request: Request) -> dict:
    db = request.app.state.db
    card = await db.one("SELECT * FROM cards WHERE id=?", (card_id,))
    if not card:
        raise HTTPException(404, "Card not found")
    result = safe(card, request, authenticated(request))
    message = await db.one(
        "SELECT text_raw,text_redacted FROM messages WHERE id=?", (card["message_id"],)
    )
    result["text"] = message["text_raw"] if authenticated(request) else message["text_redacted"]
    result["exact_location"] = authenticated(request)
    result["audit"] = await db.all(
        "SELECT ts,action,detail FROM audit_log WHERE entity='card' AND entity_id=? ORDER BY id",
        (card_id,),
    )
    result["duplicates"] = await db.all(
        "SELECT id,created_at FROM cards WHERE duplicate_of=?", (card_id,)
    )
    return result


@router.patch("/api/cards/{card_id}", dependencies=[Depends(coordinator)])
async def edit_card(card_id: int, body: CardPatch, request: Request) -> dict:
    state = request.app.state
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return {"ok": True}
    location = (
        await state.geo.resolve(fields["location_text"]) if "location_text" in fields else None
    )
    async with state.db.transaction():
        card = await state.db.one("SELECT * FROM cards WHERE id=?", (card_id,))
        if not card:
            raise HTTPException(404, "Card not found")
        await invalidate_matches(state.db, card_id, "Coordinator edited card")
        if location:
            fields.update(
                zip(("lat", "lng", "loc_source", "loc_confidence"), location, strict=True)
            )
            fields.setdefault("status", "open" if location[0] is not None else "needs_location")
        if fields.get("status") == "open" and (location[0] if location else card["lat"]) is None:
            fields["status"] = "needs_location"
        fields["updated_at"] = now()
        await state.db.execute(
            "UPDATE cards SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?",
            (*fields.values(), card_id),
        )
        await state.db.audit(
            "coordinator_edit", "card", card_id, {"fields": list(fields)}, "coordinator"
        )
        updated = await state.db.one("SELECT * FROM cards WHERE id=?", (card_id,))
        await suggest(state.db, updated, state.settings)
    state.events.publish("card_updated", {"id": card_id})
    return {"ok": True}


@router.get("/api/matches", response_model=Page)
async def matches(
    request: Request,
    status: str = "",
    limit: int = Query(100, ge=1, le=200),
    cursor: int = Query(0, ge=0),
) -> dict:
    db = request.app.state.db
    rows = await db.all(
        "SELECT * FROM matches WHERE id>?"
        + (" AND status=?" if status else "")
        + " ORDER BY id LIMIT ?",
        (cursor, status, limit + 1) if status else (cursor, limit + 1),
    )
    next_cursor = rows[limit - 1]["id"] if len(rows) > limit else None
    results = []
    for row in rows[:limit]:
        need = await db.one("SELECT * FROM cards WHERE id=?", (row["need_id"],))
        offer = await db.one("SELECT * FROM cards WHERE id=?", (row["offer_id"],))
        if not need or not offer:
            continue
        row.update(
            need=safe(need, request),
            offer=safe(offer, request),
            preview=notification(need, offer, row["distance_km"]),
            breakdown=json.loads(row["breakdown"]),
            note=redact(row["note"]),
            distance_km=round(row["distance_km"] * 2) / 2,
        )
        results.append(row)
    return {"items": results, "next_cursor": next_cursor}


@router.post("/api/matches/{match_id}/{action}", dependencies=[Depends(demo_or_coordinator)])
async def decide(match_id: int, action: str, body: Decision, request: Request) -> dict:
    if action not in {"approve", "reject", "complete", "retry"}:
        raise HTTPException(404, "Unknown match action")
    state = request.app.state
    async with state.db.transaction():
        match = await state.db.one("SELECT * FROM matches WHERE id=?", (match_id,))
        if not match:
            raise HTTPException(404, "Match not found")
        need = await state.db.one("SELECT * FROM cards WHERE id=?", (match["need_id"],))
        offer = await state.db.one("SELECT * FROM cards WHERE id=?", (match["offer_id"],))
        if not need or not offer:
            raise HTTPException(409, "Participant data was erased")
        if not need["simulated"] or not offer["simulated"]:
            coordinator(request)
        if action == "retry":
            if match["status"] != "approved" or match["notification_state"] not in {
                "failed",
                "pending",
            }:
                raise HTTPException(409, "Only an unsent approved notification can be retried")
        elif action == "complete":
            if match["status"] != "approved":
                raise HTTPException(409, "Approve this match first")
            await state.db.execute(
                "UPDATE cards SET status='fulfilled',updated_at=? WHERE id IN (?,?)",
                (now(), need["id"], offer["id"]),
            )
        else:
            if match["status"] != "suggested":
                raise HTTPException(409, "Match already decided")
            if action == "approve":
                if any(
                    c["status"] != "open" or c["possible_misinformation"] for c in (need, offer)
                ):
                    raise HTTPException(409, "Cards are no longer eligible")
                await state.db.execute(
                    "UPDATE cards SET status='matched',updated_at=? WHERE id IN (?,?)",
                    (now(), need["id"], offer["id"]),
                )
                await state.db.execute(
                    "UPDATE matches SET status='rejected',note='Resource assigned elsewhere',decided_at=? WHERE id!=? AND status='suggested' AND (need_id IN (?,?) OR offer_id IN (?,?))",
                    (now(), match_id, need["id"], offer["id"], need["id"], offer["id"]),
                )
        new_status = {
            "approve": "approved",
            "reject": "rejected",
            "complete": "completed",
            "retry": "approved",
        }[action]
        await state.db.execute(
            "UPDATE matches SET status=?,decided_at=?,decided_by='coordinator',note=? WHERE id=?",
            (new_status, now(), body.note, match_id),
        )
        await state.db.audit(action, "match", match_id, actor="coordinator")
    notification_state = match["notification_state"]
    if action in {"approve", "retry"}:
        notification_state = await state.telegram.notify_match(match, need, offer)
        async with state.db.transaction():
            await state.db.execute(
                "UPDATE matches SET notification_state=? WHERE id=?", (notification_state, match_id)
            )
            await state.db.audit("notification_" + notification_state, "match", match_id)
    state.events.publish("match_updated", {"id": match_id})
    state.events.publish("stats")
    return {"ok": True, "status": new_status, "notification_state": notification_state}


@router.get("/api/stats")
async def stats(request: Request) -> dict:
    db = request.app.state.db
    messages = await db.all(
        "SELECT processing_state,COUNT(*) n FROM messages GROUP BY processing_state"
    )
    card_counts = await db.one(
        "SELECT COUNT(*) cards_total, COALESCE(SUM(status='open'),0) cards_open, COALESCE(SUM(intent='need' AND status IN ('open','needs_location')),0) needs, COALESCE(SUM(intent='offer' AND status IN ('open','needs_location')),0) offers, COALESCE(SUM(status='duplicate'),0) duplicates_merged FROM cards"
    )
    result = card_counts | {
        "messages_processed": sum(
            r["n"] for r in messages if r["processing_state"] in {"processed", "ignored"}
        ),
        "processing": {r["processing_state"]: r["n"] for r in messages},
    }
    for row in await db.all("SELECT status,COUNT(*) n FROM matches GROUP BY status"):
        result["matches_" + row["status"]] = row["n"]
    for key in ("matches_suggested", "matches_approved", "matches_completed"):
        result.setdefault(key, 0)
    result["extractor_mix"] = {
        r["extractor"]: r["n"]
        for r in await db.all("SELECT extractor,COUNT(*) n FROM cards GROUP BY extractor")
    }
    result["by_language"] = {
        r["language"]: r["n"]
        for r in await db.all("SELECT language,COUNT(*) n FROM cards GROUP BY language")
    }
    people = await db.one(
        "SELECT COUNT(*) participants,COUNT(DISTINCT country) countries_self_reported,COALESCE(SUM(simulated),0) simulated_participants FROM participants"
    )
    result.update(people)
    timings = await db.all(
        "SELECT c.created_at,m.received_at FROM cards c JOIN messages m ON m.id=c.message_id ORDER BY c.id DESC LIMIT 1000"
    )
    result["median_seconds_message_to_card"] = (
        round(
            statistics.median(
                [
                    (
                        datetime.fromisoformat(r["created_at"])
                        - datetime.fromisoformat(r["received_at"])
                    ).total_seconds()
                    for r in timings
                ]
            ),
            3,
        )
        if timings
        else 0
    )
    result["simulation_running"] = bool(
        request.app.state.simulator.task and not request.app.state.simulator.task.done()
    )
    return result


@router.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    if len(request.app.state.events.clients) >= 100:
        raise HTTPException(503, "Event stream capacity reached; use polling")
    return StreamingResponse(
        request.app.state.events.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/ingest", dependencies=[Depends(demo_or_coordinator)])
async def ingest(body: Ingest, request: Request) -> dict:
    if not body.simulated:
        coordinator(request)
    else:
        # Public demo routing cannot collide with live Telegram identifiers.
        body.chat_id = "api-demo:" + body.chat_id
        body.sender_id = "api-demo:" + body.sender_id
    mid, created = await request.app.state.pipeline.ingest(body)
    return {"id": mid, "queued": created}


@router.post("/api/simulate/start", dependencies=[Depends(demo_or_coordinator)])
async def simulate_start(body: DrillStart, request: Request) -> dict:
    await request.app.state.simulator.start(body.speed)
    return {"ok": True}


@router.post("/api/simulate/pause", dependencies=[Depends(demo_or_coordinator)])
async def simulate_pause(request: Request) -> dict:
    await request.app.state.simulator.pause()
    return {"ok": True}


@router.post("/api/simulate/reset", dependencies=[Depends(demo_or_coordinator)])
async def simulate_reset(request: Request) -> dict:
    await request.app.state.simulator.reset()
    return {"ok": True}


@router.post("/telegram/webhook/{secret}")
async def webhook(secret: str, request: Request) -> dict:
    s = request.app.state.settings
    if (
        s.telegram_mode != "webhook"
        or not hmac.compare_digest(secret, s.telegram_webhook_secret)
        or not hmac.compare_digest(
            request.headers.get("x-telegram-bot-api-secret-token", ""), s.telegram_webhook_secret
        )
    ):
        raise HTTPException(403, "Invalid webhook secret")
    await request.app.state.telegram.handle(await request.json())
    return {"ok": True}


@router.get("/api/eval")
async def evaluation() -> dict:
    path = Path(__file__).resolve().parents[1] / "reports/eval_report.json"
    if not path.exists():
        raise HTTPException(404, "Run python scripts/eval.py to produce an evaluation report")
    return json.loads(path.read_text(encoding="utf-8"))
