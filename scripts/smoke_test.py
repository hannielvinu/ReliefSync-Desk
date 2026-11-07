"""Verify the public repository in a fresh checkout and virtual environment."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    checkout = Path(tempfile.mkdtemp(prefix="reliefsync-smoke-"))
    subprocess.run(
        ["git", "clone", "https://github.com/hannielvinu/ReliefSync-Desk.git", str(checkout)],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "venv", str(checkout / ".venv")], check=True)
    python = checkout / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=checkout, check=True
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    env.update(
        APP_ENV="development",
        DEMO_MODE="true",
        SALT=secrets.token_hex(32),
        COORDINATOR_TOKEN="",
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_MODE="polling",
        LLM_BASE_URL="",
        LLM_API_KEY="",
        LLM_MODEL="",
        DB_PATH=str(checkout / "data/smoke.db"),
        GEOCODER_URL="",
        ALLOW_FALLBACK_EXTRACTOR="true",
    )
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=checkout,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base, timeout=10) as client:
            for _ in range(60):
                try:
                    health = client.get("/health")
                    if health.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("Clean-install server did not become healthy")
            assert client.get("/").status_code == 200
            assert client.post("/api/simulate/start", json={"speed": 10}).status_code == 200
            for _ in range(20):
                time.sleep(2)
                stats = client.get("/api/stats").json()
                if not stats["simulation_running"]:
                    break
            cards = client.get("/api/cards").json()["items"]
            matches = client.get("/api/matches").json()["items"]
            insulin = next(
                m
                for m in matches
                if m["need"]["item_en"] == "insulin" and m["offer"]["item_en"] == "insulin"
            )
            approved = client.post(f"/api/matches/{insulin['id']}/approve", json={})
            assert (
                approved.status_code == 200
                and approved.json()["notification_state"] == "would_send"
            )
            assert client.post(f"/api/matches/{insulin['id']}/complete", json={}).status_code == 200
            assert all(c["simulated"] for c in cards)
            assert not any("00000" in c["message_en"] for c in cards)
            assert stats["processing"].get("failed", 0) == 0
            report = {
                "source": "Fresh clone of public GitHub repository",
                "commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
                ).strip(),
                "python": sys.version.split()[0],
                "health": health.json(),
                "stats": stats,
                "cards": len(cards),
                "matches": len(matches),
                "insulin_approval": approved.json(),
                "completed": True,
                "secrets_configured": False,
                "checkout": str(checkout),
            }
            (ROOT / "reports/clean_clone_smoke.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps(report, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
