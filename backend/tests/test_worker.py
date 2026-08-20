from app.workers.tasks import ping


async def test_ping_job() -> None:
    assert await ping({}) == "pong"
