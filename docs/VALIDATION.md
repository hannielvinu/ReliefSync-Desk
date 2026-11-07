# Delivery verification — 7 November 2026

## What was delivered

P0–P3: repository/bootstrap, pinned installed dependencies, configuration, SQLite/WAL schema, redaction/auth/fuzzing, locality lookup, validated provider extraction and offline rules.

P4–P7: queue workers, triage/dedupe/incident grouping, resource scoring, transactional approval/completion, Telegram polling/webhooks/commands/edits/pins, public-safe REST API/SSE, and a 45-message simulated drill.

P8–P11: buildless responsive dashboard, map/drawer/matches, shared four-language UI, theme controls, five supporting pages, 65 labelled synthetic evaluation messages and actual generated evaluation reports.

P12–P14: non-root production Docker image, Compose/Caddy, Ubuntu setup script/systemd option, CI including production-container execution, full deployment/safety/demo/submission documentation, screenshots, a real local recording, regression checks and fresh-clone testing.

## Executed checks

| Check | Actual result |
| --- | --- |
| Ruff lint | Passed |
| Ruff format | Passed |
| Local pytest, Python 3.11.4 / Windows | **59 passed**, **95.71%** app statement coverage; 80% gate passed |
| GitHub CI, Ubuntu / Python 3.12 | Passed tests, formatting, evaluation and container loop |
| Production Docker + Caddy | Built and started with strong generated test secrets; public-proxy health and simulated insulin approval/completion passed |
| Fresh public clone / new venv / pinned runtime install / no keys | Healthy startup; **44 persisted messages** from 45 updates (one edit), **40 cards**, **24 suggestions**, **0 failed messages**; insulin approval and completion passed |
| Browser layouts | Six pages × five specified viewport sizes, plus Tamil mobile: **31 checks**, no horizontal overflow |
| Browser JavaScript | No observed uncaught errors |
| Screenshots | Desktop/mobile, light/dark, suggested match, approval dialog, drawer, supporting pages, Tamil mobile |
| Video | `reports/demo-walkthrough.webm`, actual silent recording of the local simulated UI; ignored by Git |
| App JavaScript | About 49.5 KB uncompressed after formatting, excluding vendored libraries |

CI evidence: [production container run](https://github.com/hannielvinu/ReliefSync-Desk/actions/runs/42379663837). Machine-readable reports: `reports/coverage.json`, `reports/browser_checks.json`, `reports/clean_clone_smoke.json`.

The clean-clone report records the exact tested revision. Subsequent delivery changes harden HTTP error consistency/read limits, format frontend sources and add evidence/documentation; CI runs again on each push. The standalone Ubuntu provisioning script and real DNS/HTTPS require a Vultr host; Compose/Caddy execution in CI does not prove those external steps.

## Evaluation, actually executed

Command: `python scripts/eval.py`. Dataset: **65 synthetic messages**. Extractor counts: **fallback 65, real provider 0**.

| Metric | Result |
| --- | --- |
| Intent | 98.5% |
| Category | 98.5% |
| Canonical resource | 98.5% |
| Location | 98.5% |
| Urgency within ±1 | 100% |
| Misinformation | 100% |

Source of truth: `reports/eval_report.json`; full per-language results and all failures are included. These are template-based smoke checks, not a held-out real-world benchmark. The report’s latency is local rule execution only, not Telegram/provider/network latency.

## Git verification

Delivery uses eight meaningful commits including the final evidence/source-formatting commit. The requested 30–50 target was not met; commits were not artificially split. All are authored and committed by **Hanniel Vinu <hannielvinu@gmail.com>**. No history rewriting or backdating was used.

Verified implementation history before the final delivery commit:

```text
c95be58 | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | ci: exercise production containers and reverse proxy
b13affb | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | fix: guard notification retries and serve API docs locally
746b199 | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | docs: provide deployment safety and submission guides
dc1eda0 | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | test: verify dispatch workflow privacy and responsive layouts
e1a5e10 | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | feat: add dispatch dashboard simulation and evaluation pages
e6bdeb0 | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | feat: implement multilingual extraction triage and Telegram intake
f6860cc | author: Hanniel Vinu <hannielvinu@gmail.com> | committer: Hanniel Vinu <hannielvinu@gmail.com> | chore: bootstrap configuration database and security foundations
```

Commit-message attribution/coauthor scan: **clean**. No `.env`, database or environment directory is tracked. Code was pushed to `origin/main`. Run `git log --format='%h | author: %an <%ae> | committer: %cn <%ce> | %s'` for the complete final history.

## Owner steps still required

The owner confirmed that no Vultr account/server or Telegram bot exists yet. These steps cannot be completed without those accounts:

1. Create a Vultr Compute Ubuntu instance, configure SSH/firewall/DNS, run `deploy/setup_vultr.sh`, and verify the real public HTTPS URL. See `deploy/DEPLOY.md`.
2. Create a Telegram bot in BotFather using `/newbot`, disable privacy using `/setprivacy`, add it to the test group, set its token and username in the ignored `.env`, restart, then execute the real two-user group acceptance test.
3. If claiming provider extraction, obtain a provider key, configure base URL/model/key, and rerun evaluation and the real intake test. Otherwise explicitly retain fallback disclosure.
4. Add an actual test-group invite and optional feedback URL. Run a consenting fictional cohort drill if desired; do not claim simulated counts as adoption.
5. Obtain independent native Tamil review using `docs/TAMIL_REVIEW.md`. Implementation review is complete; native sign-off is not.
6. Upload the local recording or make a narrated final live recording, add actual live/video URLs in README and `docs/SUBMISSION.md`, check the official event’s current requirements, and submit through the owner’s Vultr Community account.

No public deployment, bot creation, live provider call, native-speaker approval, student cohort or portal submission has been claimed. The local simulated system and tested deployment package are delivered; external-account activation remains pending.
