#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo 'Run as root with sudo.'; exit 1; fi
source /etc/os-release
if [[ ${ID} != ubuntu ]]; then echo 'Ubuntu 22.04/24.04 is required.'; exit 1; fi
apt-get update
apt-get install -y ca-certificates curl git ufw python3
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch=$(dpkg --print-architecture)
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$arch" "$VERSION_CODENAME" >/etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
directory=/opt/reliefsync
if [[ ! -d "$directory/.git" ]]; then
  git clone https://github.com/hannielvinu/ReliefSync-Desk.git "$directory"
fi
cd "$directory"
if [[ ! -f .env ]]; then
  umask 077
  cp .env.example .env
  python3 - <<'PY'
import os, secrets
from pathlib import Path
path = Path('.env')
text = path.read_text().replace('APP_ENV=development', 'APP_ENV=production')
text = text.replace('\nSALT=\n', '\nSALT=' + secrets.token_hex(32) + '\n')
text = text.replace('\nCOORDINATOR_TOKEN=\n', '\nCOORDINATOR_TOKEN=' + secrets.token_urlsafe(32) + '\n')
if os.environ.get('PUBLIC_BASE_URL'):
    text = text.replace('PUBLIC_BASE_URL=http://localhost:8000', 'PUBLIC_BASE_URL=' + os.environ['PUBLIC_BASE_URL'])
if os.environ.get('SITE_ADDRESS'):
    text = text.replace('SITE_ADDRESS=:80', 'SITE_ADDRESS=' + os.environ['SITE_ADDRESS'])
path.write_text(text)
PY
  echo 'Created .env with random private secrets. Edit it to connect Telegram and your extraction provider.'
fi
chmod 600 .env
docker compose up -d --build --wait
curl --fail --silent http://127.0.0.1:8000/health
echo
echo 'Desk is running. See deploy/DEPLOY.md to configure HTTPS, Telegram, backups and testing.'
