from pydantic import BaseModel, Field
from typing import Any, Optional


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[int] = None
    limit: Optional[int] = Field(default=None, ge=1, le=50)
    stream: bool = False


class AgentSource(BaseModel):
    text: str
    score: float
    metadata: dict[str, Any] | None = None


class AgentToolTrace(BaseModel):
    name: str
    status: str
    summary: str


class AgentChatResponse(BaseModel):
    signal: str
    answer: str
    session_id: int
    sources: list[AgentSource] = []
    tool_trace: list[AgentToolTrace] = []


class AgentMessageResponse(BaseModel):
    message_id: int
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str | None = None


class AgentSessionResponse(BaseModel):
    session_id: int
    project_id: int
    user_id: int
    title: str
    created_at: str | None = None
    updated_at: str | None = None


class AgentSessionDetailResponse(AgentSessionResponse):
    messages: list[AgentMessageResponse] = []
