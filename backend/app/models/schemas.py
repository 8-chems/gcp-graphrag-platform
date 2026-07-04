from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None


class SourceChunk(BaseModel):
    content: str
    source: str
    score: float


class GraphFact(BaseModel):
    subject: str
    relation: str
    object: str


class AgentTrace(BaseModel):
    agent: str
    action: str
    detail: str


class ChatResponse(BaseModel):
    answer: str
    used_agents: list[str]
    sources: list[SourceChunk] = []
    graph_facts: list[GraphFact] = []
    trace: list[AgentTrace] = []
    session_id: str


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    entities_extracted: int
    relationships_extracted: int
    status: Literal["queued", "processing", "completed", "failed"]


class DocumentSummary(BaseModel):
    id: str
    filename: str
    gcs_path: str
    status: str
    chunks_created: int
    entities_extracted: int
    relationships_extracted: int
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    environment: str
    timestamp: datetime
    dependencies: dict[str, Any]
