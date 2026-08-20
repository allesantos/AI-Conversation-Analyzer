from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(slots=True, frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    model: str
    provider: str


@dataclass(slots=True, frozen=True)
class LLMStructuredResult:
    data: BaseModel
    usage: LLMUsage
