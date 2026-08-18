"""副驾只读工具白名单。无写操作。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.quant.ai.guard import wrap_untrusted_evidence

READONLY_TOOLS = (
    "get_fund_flow",
    "get_research_snapshot",
    "search_news",
    "preview_strategy",
    "get_backtest_report",
    "get_report_card",
)


def execute_tool(name: str, arguments: dict[str, Any], *, handlers: dict[str, Callable]) -> dict:
    if name not in READONLY_TOOLS:
        return {"ok": False, "error": "tool_not_allowed"}
    if "DROP TABLE" in str(arguments).upper() or "ignore previous" in str(arguments).lower():
        return {"ok": False, "error": "rejected_untrusted_arguments"}
    handler = handlers[name]
    result = handler(**arguments)
    if isinstance(result, str):
        result = {"text": wrap_untrusted_evidence(result)}
    return {"ok": True, "tool": name, "result": result}
