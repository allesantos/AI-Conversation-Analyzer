import pytest

from app.ai.rag.strategy import determine_context_strategy
from app.ai.rag.types import ContextStrategy
from app.core.config import Settings


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1999, ContextStrategy.DIRECT),
        (2000, ContextStrategy.DIRECT),
        (2001, ContextStrategy.SUMMARY_SELECTION),
        (9999, ContextStrategy.SUMMARY_SELECTION),
        (10000, ContextStrategy.SUMMARY_SELECTION),
        (10001, ContextStrategy.RAG),
    ],
)
def test_determine_context_strategy_boundaries(count: int, expected: ContextStrategy) -> None:
    settings = Settings()
    assert determine_context_strategy(count, settings) is expected
