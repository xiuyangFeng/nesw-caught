from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


# 财报 / 事件日历事件类型。当前仅覆盖财报日与除息日两类。
CalendarEventType = Literal["earnings", "ex_dividend"]


class CalendarEventView(BaseModel):
    """单条即将到来的日历事件。"""

    symbol: str
    display_name: str | None = None
    event_type: CalendarEventType
    # ISO 日期字符串（YYYY-MM-DD），前端按日期分组展示。
    date: str
    # 距今天数（>=0 表示今天或未来）。
    days_until: int


class CalendarSymbolSummaryView(BaseModel):
    """单只自选股的“最近一次未来财报”摘要，供卡片角标使用。"""

    symbol: str
    display_name: str | None = None
    next_earnings_date: str | None = None
    next_earnings_days_until: int | None = None


class CalendarResponseView(BaseModel):
    """日历接口统一返回体，同时服务全量与单只查询。"""

    # 前视窗口天数（events 仅包含窗口内事件）。
    days: int
    # 按日期升序排列的即将到来事件。
    events: list[CalendarEventView] = Field(default_factory=list)
    # 每只 symbol 的最近未来财报摘要（不受窗口限制，用于角标倒计时）。
    summaries: list[CalendarSymbolSummaryView] = Field(default_factory=list)
    # 拉取失败被优雅跳过的 symbol 数量。
    skipped_count: int = 0
    generated_at: UTCDateTime
