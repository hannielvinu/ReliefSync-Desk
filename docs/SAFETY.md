# Safety, privacy and threat model

Not an emergency service. Contact local emergency services first. Do not rely on this prototype for medical decisions, guaranteed rescue or identity verification.

## Trust boundaries

All messages are untrusted text. The extraction service receives them as user content with a fixed system prompt, no tools and a validated output schema. Neither provider outputs nor participant text are executed or rendered as HTML. API writes require coordinator auth or the narrowly bounded simulated-demo exception. Cross-origin writes are rejected. Cookies are HttpOnly, SameSite=Lax, signed and expire in 12 hours; HTTPS enables Secure. No secrets are stored in browser preferences. Only theme/language preferences use localStorage.

Public API serializers hide private Telegram routing identifiers and sender hashes, redact common contacts/addresses, and replace exact coordinates with deterministic positions inside a 0.005-degree grid cell. Exact positions and original text are available only in authenticated coordinator detail. Public location names come from broad locality areas, not raw sender addresses. Provider summary and extracted item text are also redacted.

## Threats and implemented controls

| Threat | Implemented mitigation | Residual risk |
| --- | --- | --- |
| Spam and flooding | IP/sender token buckets, login limit, bounded queue, body/text caps, finite event clients | Limits are single-process; determined distributed attackers can overwhelm a small host |
| Prompt injection | Fixed prompt, message only in user role, schema key/type validation, retry, injection prefilter, no execution | New linguistic attacks may evade rules or produce inaccurate extraction |
| Doxxing vulnerable people | Contact/address redaction, hashed grouping IDs, no public raw routing IDs, fuzzed positions, authenticated detail | Heuristic redaction misses formats; approximate areas can still be identifying |
| Predators posing as volunteers | No automatic dispatch, coordinator review, exact notification preview, no public exact location | No identity/background checking or verified availability; coordinators must verify both parties |
| Misinformation | Flagging and exclusion from matching, separate flagged filter | Novel rumours may evade detection; flags can be false positives |
| Wrong matches | Category/item gate, location requirement, radius cap, distinct senders, visible breakdown, human approval | Similar resources may have incompatible specifications; quantities are not allocated partially |
| Extraction errors | Confidence and extractor labels, capped fallback confidence, editable cards, evaluation | Confidence is not calibrated medical/operational assurance |
| Resource double allocation | Transactional approval and rejection of conflicting suggestions | App cannot prevent commitments made outside the system |
| Stolen coordinator secret | Production strength requirements, constant-time comparison, signed HttpOnly session, HTTPS setup | Shared-token roles do not support individual revocation or per-user accountability |
| Integration outage | Retry, circuit breaker, durable intake, delivery status, explicit notification retry | Exactly-once external delivery and availability are not guaranteed |

The supplied Valencia reporting documents a fake alternative emergency number: [The Star](https://thestar.com.my/tech/tech-news/2024/11/08/online-disinformation-exacerbates-spain-flood-disaster). This app never supplies invented official numbers or claims official integration.

## Storage and deletion

The database contains raw text and private Telegram IDs for routing, plus redacted text, structured fields, coordinates and an audit trail. Optional country information is self-reported. When configured, the extraction provider can receive message content; operators are responsible for its retention policy and participant consent. Remote geocoding is opt-in, restricted to locality queries and should never receive personal/confidential content.

`/forget` deletes a sender’s messages/cards/participation record, rejects related matches, and reopens a surviving reserved partner. It cannot remove previously posted Telegram messages, external provider copies or old operator backups. Demo reset and `python scripts/seed_demo.py --purge-simulated` remove fictional data only (stop the app before CLI purge). No automatic age-based deletion is claimed; operators must choose and apply a short retention policy and backup expiry appropriate to their test.

Do not expose database files, backups or `.env` through a web directory. The app serves only `static/`; deployments keep a separate runtime volume. Encrypt host storage/backups if needed. Logs exclude message content and bot/API tokens. Uvicorn access logs are disabled so webhook secret paths cannot enter them.

## Before real use

This prototype lacks verified volunteer identities, granular roles, independent security/accessibility review, clinical validation, high availability, cross-service deletion guarantees and a real-world evaluation. Keep testing fictional and consent-based until these operational gaps are addressed. Human review is necessary but does not eliminate those risks.
