# Deploy on Vultr Compute

No live deployment is claimed by this repository. Development ran Windows/Python 3.11. The production Docker Compose image, Caddy proxy and simulated dispatch loop passed Ubuntu/Python 3.12 GitHub CI. A Vultr account/host was unavailable; validate the setup script, DNS and public HTTPS on the target host before sharing its URL.

## 1. Create the host

Create a Vultr account and choose a Compute instance with Ubuntu **24.04 LTS** (22.04 is also supported by the setup script). A small instance is sufficient for a controlled demo; choose capacity and region yourself. Add your SSH public key and configure a Vultr firewall allowing TCP 22 (preferably only your IP), 80 and 443. Retain the server IP. Instance billing is controlled by your Vultr account.

SSH as root (or a sudo-capable user): `ssh root@YOUR_SERVER_IP`. Keep the current SSH session open while changing firewall settings. The setup script permits port 22; adjust it first if your SSH service uses another port.

```bash
git clone https://github.com/hannielvinu/ReliefSync-Desk.git
cd ReliefSync-Desk
sudo env PUBLIC_BASE_URL=http://YOUR_SERVER_IP bash deploy/setup_vultr.sh
```

The script installs Docker from its official Ubuntu apt repository, permits 22/80/443 in UFW, clones the application to `/opt/reliefsync`, creates a private `.env` with random secrets on first run, and starts Compose. Repeated runs preserve `.env` and data. It does not automatically pull newer code; use the update procedure below. The app volume is separate from the code and survives rebuilds.

## 2. Configure HTTPS

Point a domain A record to the server IP. Alternatively, use an IP-based hostname offered by a service such as sslip.io, subject to that service’s availability and ACME limits. Example pattern: `YOUR-IP-WITH-DASHES.sslip.io`. Verify DNS yourself; no hostname is pre-registered by this project.

In `/opt/reliefsync/.env` set:

```dotenv
PUBLIC_BASE_URL=https://desk.example.org
SITE_ADDRESS=desk.example.org
```

Run `sudo docker compose up -d --force-recreate` from `/opt/reliefsync`. Caddy obtains HTTPS automatically when DNS and ports are correct. `SITE_ADDRESS=:80` is the plain HTTP-by-IP fallback. HTTP is suitable only for an initial simulated demo; configure HTTPS before entering coordinator credentials or connecting real intake.

## 3. Connect services

Edit `/opt/reliefsync/.env` with a terminal editor; keep mode 600. Never put secrets in screenshots, Git, a public issue or the command line.

- Telegram: [BotFather and privacy setup](../docs/TELEGRAM_SETUP.md). Set token, username, `TELEGRAM_MODE=polling`, and optional group link.
- Provider: obtain an API key from your chosen provider account. Set `LLM_BASE_URL` (typically ending in `/v1`), `LLM_MODEL`, `LLM_API_KEY`; confirm the model supports Chat Completions and optional JSON object mode. No provider or model is hardcoded. Provider billing belongs to your account.
- Set `TEST_GROUP_URL` and `FEEDBACK_URL` if you have them. They are optional.
- For a public hackathon demo leave `DEMO_MODE=true`. Unauthenticated users can change simulated matches only. Real Telegram cards still require coordinator login. For private operations use `DEMO_MODE=false`.
- Keep the generated SALT stable. Changing it prevents prior senders from finding their old records via `/forget` and invalidates sessions.

Restart with `sudo docker compose up -d --force-recreate`. Environment changes require recreation; `docker compose restart` alone does not reload env_file values.

## 4. Verify the deployed loop

```bash
cd /opt/reliefsync
sudo docker compose ps
curl --fail http://127.0.0.1:8000/health
curl --fail https://desk.example.org/health
sudo docker compose logs --tail=100 app
```

Open the external URL in another network/browser. Run a 10× drill; confirm an insulin pair appears, approve it, check `would_send`, then complete. All drill cards must show Simulated. Confirm `/eval` loads the checked-in report, and `/join` displays configured links. Log in as coordinator using the generated COORDINATOR_TOKEN from the private file. Test Telegram with two consenting users and fictional needs/offers. Confirm a suggested connection sends nothing until approval, then posts only a resource, approximate area and user mentions. Test `/forget`. With provider credentials configured, inspect card `extractor` labels and rerun evaluation locally or inside the container with scripts mounted/copied; the deployed checked-in evaluation does not change just because a key was added.

Record the actual public URL in README and docs/SUBMISSION.md only after these checks succeed. Do not describe mocked transport as a live test.

## Updates and logs

```bash
cd /opt/reliefsync
sudo git pull --ff-only
sudo docker compose up -d --build --wait
sudo docker compose logs --tail=100 app caddy
```

Do not use `docker compose down -v` unless deliberately deleting all data. The deployment exposes port 8000 on loopback only. Proxy headers are trusted only because public traffic must enter through Caddy; do not publish the application container port on all interfaces. Keep one application worker and one polling owner.

## Consistent backups

Use SQLite’s online backup API, not a plain copy of the database while WAL writes are active:

```bash
sudo docker compose exec -T app python -c "import sqlite3; s=sqlite3.connect('/app/runtime/reliefsync.db'); d=sqlite3.connect('/app/runtime/backup.sqlite'); s.backup(d); d.close(); s.close()"
sudo docker compose cp app:/app/runtime/backup.sqlite ./backup.sqlite
sudo chmod 600 backup.sqlite
```

Store backups privately and set a short retention policy. `/forget` does not erase old backup copies. For restoration, stop the app, back up its current volume, replace the database through a maintenance container as UID 10001, remove matching stale WAL/SHM files, then restart and verify. Never overwrite an open SQLite database. Test restoration on a separate instance first.

## Optional Python/systemd path

Create service user `reliefsync`, clone to `/opt/reliefsync`, install Python venv packages and pinned dependencies, create `/opt/reliefsync/.venv`, and make `data/` writable by the service user. Install `deploy/reliefsync.service` into `/etc/systemd/system/`. Use a host Caddy reverse proxy to `127.0.0.1:8000` (the Compose Caddyfile’s upstream `app:8000` is container-only). Set `DB_PATH=/opt/reliefsync/data/reliefsync.db`. Enable using `sudo systemctl enable --now reliefsync`. Do not run Compose and systemd intake concurrently with the same Telegram token.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Container exits before startup | Production SALT and token length; webhook secret; `.env` syntax; logs |
| HTTPS fails | DNS A/AAAA, Vultr firewall, UFW, ports, Caddy logs, ACME rate limits |
| 502 / app unhealthy | `docker compose logs app`, database volume permissions, `/health` on loopback |
| Bot sees only commands | BotFather `/setprivacy` Disable, remove/re-add bot, inspect `/status` warning |
| Telegram 409 conflict | Stop the other polling instance; polling startup deletes a previous webhook |
| Card says Fallback | Missing provider config, wrong `/v1` URL/model, timeout, schema mismatch or circuit breaker |
| No matches | Two different senders, same resource/category, same simulation status, known locations within radius, unassigned cards |
| Notification failed | Bot group access, group ID, connectivity; use explicit retry after checking group history |
| 429 errors | App IP/sender/login limits; confirm Caddy forwarding and avoid public port 8000 |
| Map unavailable | OSM is best effort; board remains usable; do not bulk-fetch tiles |
| No country counts | Optional `/iam <country>` only; simulated drill does not invent countries |
