from typing import Literal
from uuid import UUID

from sqlmodel import Field, SQLModel


class AskRequest(SQLModel):
    question: str = Field(min_length=3, max_length=1000)
    equipment_id: UUID | None = Field(default=None, description="Search this machine's manuals plus general ones")


class DiagnoseRequest(SQLModel):
    symptom: str = Field(min_length=3, max_length=1000)


class Source(SQLModel):
    n: int                       # the [n] the answer cites
    document_id: UUID
    title: str
    doc_type: str
    page: int | None
    excerpt: str
    matched_by: list[str]        # which channels found it: "code", "words", "meaning"
    similarity: float
    cited: bool                  # did the answer actually cite it


class AIAnswer(SQLModel):
    answer: str
    # llm: generated from the sources. extractive: no LLM was available, so the top excerpts are returned.
    # not_found: nothing relevant in the manuals (and no LLM call was made).
    mode: Literal["llm", "extractive", "not_found"]
    confidence: Literal["high", "medium", "none"]   # from retrieval scores, never the LLM's self-assessment
    model: str | None
    sources: list[Source]
    latency_ms: int
