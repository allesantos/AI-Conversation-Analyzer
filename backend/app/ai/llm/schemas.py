from pydantic import BaseModel, Field


class ConversationSummaryOutput(BaseModel):
    summary: str = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)


class AskAnswerOutput(BaseModel):
    answer: str = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
