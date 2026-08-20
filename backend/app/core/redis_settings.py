from urllib.parse import urlparse

from arq.connections import RedisSettings


def redis_settings_from_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    database = 0
    if parsed.path and parsed.path != "/":
        database = int(parsed.path.lstrip("/").split("/")[0] or 0)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
    )
