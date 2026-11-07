import asyncio
import json
import secrets
from pathlib import Path

from app.models import Ingest
from app.pipeline import Pipeline


class Simulator:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.task: asyncio.Task | None = None
        self.position = 0
        self.run_id = secrets.token_hex(6)
        self.scenario = json.loads(
            (Path(__file__).resolve().parents[1] / "data/scenarios/storm_drill.json").read_text(
                encoding="utf-8"
            )
        )

    async def start(self, speed: int = 3) -> None:
        if self.task and not self.task.done():
            return
        if self.position >= len(self.scenario):
            self.position = 0
            self.run_id = secrets.token_hex(6)
        self.task = asyncio.create_task(self.play(speed))

    async def play(self, speed: int) -> None:
        while self.position < len(self.scenario):
            row = self.scenario[self.position]
            previous = self.scenario[self.position - 1]["at"] if self.position else 0
            await asyncio.sleep(max(0, row["at"] - previous) / speed)
            payload = {k: v for k, v in row.items() if k != "at"}
            payload.update(
                simulated=True,
                chat_id="drill-" + self.run_id,
                sender_id=self.run_id + "-" + row.get("sender_id", str(self.position)),
            )
            await self.pipeline.ingest(Ingest(**payload))
            self.position += 1

    async def pause(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def reset(self) -> None:
        await self.pause()
        await self.pipeline.queue.join()
        await self.pipeline.db.purge_simulated()
        self.position = 0
        self.run_id = secrets.token_hex(6)
        self.pipeline.events.publish("card_updated")
