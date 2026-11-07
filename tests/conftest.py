import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def desk(tmp_path):
    settings = Settings(
        _env_file=None, db_path=str(tmp_path / "test.db"), salt="s" * 32, coordinator_token="c" * 32
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client


async def intake(app, client, text, sender="test", **kwargs):
    response = await client.post("/api/ingest", json={"text": text, "sender_id": sender, **kwargs})
    assert response.status_code == 200, response.text
    await app.state.pipeline.queue.join()
    return response.json()
