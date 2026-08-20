from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis_settings import redis_settings_from_url
from app.workers.tasks import generate_embeddings, generate_transcription, ping

settings = get_settings()
configure_logging(debug=settings.debug)


class WorkerSettings:
    functions = [ping, generate_embeddings, generate_transcription]
    redis_settings = redis_settings_from_url(settings.redis_url)
    job_timeout = 300
    max_jobs = 10
