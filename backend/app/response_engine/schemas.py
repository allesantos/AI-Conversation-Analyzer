from pydantic import BaseModel, Field


class SuggestionItem(BaseModel):
    category: str = Field(description="NATURAL, DIVERTIDA, DIRETA ou CONSERVADORA")
    text: str = Field(min_length=1, description="Texto sugerido de resposta")


class ResponseSuggestionsOutput(BaseModel):
    suggestions: list[SuggestionItem] = Field(
        min_length=4,
        max_length=4,
        description="Exatamente 4 sugestões, uma por categoria",
    )
