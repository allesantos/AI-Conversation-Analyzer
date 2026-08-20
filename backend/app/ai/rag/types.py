from enum import StrEnum


class ContextStrategy(StrEnum):
    DIRECT = "DIRECT"
    SUMMARY_SELECTION = "SUMMARY_SELECTION"
    RAG = "RAG"


class EmbeddingJobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
