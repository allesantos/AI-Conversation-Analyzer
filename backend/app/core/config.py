from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Conversation Analyzer"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://aca:aca@localhost:55432/aca"
    redis_url: str = "redis://localhost:56379/0"

    jwt_secret: str = "change-me-in-development-min-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    cors_origins: str = "http://localhost:14200"

    demo_owner_email: str = "alledesenvolvimento@gmail.com"
    demo_contact_email: str = "alledesenvolvimento@gmail.com"
    demo_unlocked_monthly_llm_calls: int = 20
    demo_unlocked_monthly_transcription_seconds: int = 600

    openai_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str = "openai"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 64
    rag_chunk_size: int = 8
    rag_top_k: int = 12
    rag_intermediate_max_messages: int = 800
    rag_intermediate_recent_messages: int = 400
    transcription_model: str = "whisper-1"
    transcription_provider: str = "openai"
    audio_storage_path: str = "storage/audio"

    rag_direct_max_messages: int = 2000
    rag_summary_max_messages: int = 10_000
    conversation_gap_hours: int = 4
    max_upload_bytes: int = 50 * 1024 * 1024
    max_zip_upload_bytes: int = 100 * 1024 * 1024
    max_zip_files: int = 500
    max_zip_uncompressed_bytes: int = 250 * 1024 * 1024
    import_batch_size: int = 500

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
