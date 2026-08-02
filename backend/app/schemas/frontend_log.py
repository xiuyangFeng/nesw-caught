from typing import Any, Literal

from pydantic import BaseModel, Field


class FrontendLogEntry(BaseModel):
    level: Literal["warn", "error"] = "error"
    message: str
    stack: str | None = None
    url: str | None = None
    # 前端本地时间戳（ISO 字符串）。仅作为消息内容记录，服务端日志时间为准。
    ts: str | None = None
    context: dict[str, Any] | None = None


class FrontendLogBatch(BaseModel):
    entries: list[FrontendLogEntry] = Field(default_factory=list)


class FrontendLogIngestResult(BaseModel):
    accepted: int
    dropped: int
