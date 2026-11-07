import asyncio
import json
from collections.abc import AsyncIterator


class EventBroker:
    def __init__(self) -> None:
        self.clients: set[asyncio.Queue] = set()

    def publish(self, event: str, data: dict | None = None) -> None:
        for queue in tuple(self.clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait((event, data or {}))

    async def stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.clients.add(queue)
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
                except TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            self.clients.discard(queue)
