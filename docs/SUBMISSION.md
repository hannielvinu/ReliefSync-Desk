# Submission draft

**Title:** ReliefSync Desk — from chat chaos to coordinated rescue

**Track:** Civic and Real-World Impact

**Repository:** https://github.com/hannielvinu/ReliefSync-Desk

**LIVE DEMO URL:** (to be added after verified Vultr deployment)

**VIDEO URL:** (upload the recording and add its real URL)

## Description

During floods, volunteer coordinators often receive requests and offers through busy community chats. Reports from Chennai describe difficulty reaching civic helplines, repeat requests and coordination problems. ReliefSync Desk explores one practical response: a shared dispatch desk that turns multilingual text into structured, reviewable action.

The application receives Telegram messages or a clearly labelled fictional storm drill. It extracts needs and offers, resource categories, urgency, locations and confidence. Same-sender repeats are grouped while separate senders remain distinct. Compatible nearby resources become suggested connections, with a transparent score breakdown and a preview of the exact notification. A human coordinator approves every connection before the bot contacts the originating chat. Approval reserves both cards, prevents conflicting assignments and leaves an audit trail.

The dashboard combines a request board, approximate-location map, suggestions and operating statistics. Shared controls support English, Tamil, Spanish and German, with examples in Tanglish as well. Public views redact common contacts and obscure exact positions. The system includes deletion commands, misinformation flags and explicit simulation labels.

The backend uses FastAPI, SQLite and asynchronous workers, with raw Telegram Bot API integration and a configurable Chat Completions extractor. Without provider credentials, visibly labelled offline rules keep the demo runnable. A reproducible synthetic evaluation reports actual extraction results and identifies the extractor used.

This is a working local prototype with tested mocked integrations and deployment assets for Vultr Compute. It is not an emergency service, does not verify volunteers, and makes no field-deployment or adoption claim. Live hosting and Telegram verification must be completed before submitting their links.

## Technical stack and design

Python 3.11+/3.12 container, FastAPI, Uvicorn, Pydantic v2, aiosqlite WAL, httpx, RapidFuzz; vanilla HTML/CSS/ES modules; vendored Leaflet and self-hosted fonts; OSM; Docker Compose and Caddy on Vultr Ubuntu Compute; pytest/respx, Ruff and Playwright.

Telegram/simulation → durable queue → validated extraction → pin/gazetteer/optional geocoder → triage/dedupe → nearby suggestions → human approval → notification/audit. [Architecture SVG](architecture.svg), [system documentation](ARCHITECTURE.md), [screenshots](screenshots/).

## Real vs simulated disclosure

Real executed local workflow, database, API, browser UI and synthetic evaluation. Telegram/provider transport verified with HTTP mocks, pending live accounts. Drill requests and participants are fictional. Current evaluation uses fallback only. No paid host, public URL, live Telegram group, real volunteer adoption or independent native Tamil review is claimed. The local silent video is an actual recording of the simulated UI, not a deployed-service recording.

## Before submitting on Vultr Community

- [x] Public source repository and license
- [x] Core local workflow, evaluation, tests and browser screenshots
- [x] Architecture diagram and user-flow documentation
- [x] Vultr setup script, Docker/Caddy configuration and deployment guide
- [ ] Create Vultr account/instance and verify final public URL
- [ ] Create bot with BotFather, disable privacy, run consenting real Telegram test
- [ ] Configure provider API key and run a labelled live-provider evaluation if claiming it
- [ ] Obtain independent Tamil review
- [ ] Upload final demo video and paste its actual link
- [ ] Recheck the official event’s current deadline, eligibility and portal requirements in the owner’s account
- [ ] Submit on Vultr Community using the owner’s account

No portal submission has been made. Do not submit the placeholders or claim completion of unchecked steps.
