import argparse
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--purge-simulated", action="store_true", help="Stop the app before purging"
    )
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    if args.purge_simulated:
        db = Database(Settings().db_path)
        await db.open()
        await db.purge_simulated()
        await db.close()
        print("Simulated data purged")
    else:
        async with httpx.AsyncClient() as client:
            response = await client.post(args.url + "/api/simulate/start", json={"speed": 10})
            response.raise_for_status()
            print("Storm drill started; all messages simulated")


if __name__ == "__main__":
    asyncio.run(main())
