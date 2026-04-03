from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    doc_id: str
    type: str  # "faq" | "glossary"
    title: str
    score: float
    source: str | None = None
    source_label: str | None = None
    source2: str | None = None
    source2_label: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)
    expanded_query: str | None = None
