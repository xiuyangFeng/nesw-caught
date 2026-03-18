from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
TOKEN_REFRESH_BUFFER_SECONDS = 300


@dataclass
class FeishuToken:
    access_token: str
    expires_at: float


@dataclass
class FeishuClient:
    app_id: str
    app_secret: str
    timeout: float = 10.0
    _token: FeishuToken | None = field(default=None, init=False, repr=False)

    def _get_tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token.expires_at - TOKEN_REFRESH_BUFFER_SECONDS:
            return self._token.access_token

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                FEISHU_TOKEN_URL,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"get token failed: {data.get('msg', 'unknown')}")

        expire_seconds = data.get("expire", 7200)
        self._token = FeishuToken(
            access_token=data["tenant_access_token"],
            expires_at=now + expire_seconds,
        )
        return self._token.access_token

    def send_card(
        self,
        target_type: str,
        target_id: str,
        card: dict[str, Any],
    ) -> dict[str, Any]:
        token = self._get_tenant_access_token()
        receive_id_type = "chat_id" if target_type == "chat" else "open_id"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                FEISHU_MESSAGE_URL,
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": target_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card, ensure_ascii=False),
                },
            )
            resp.raise_for_status()
            result = resp.json()

        if result.get("code") != 0:
            raise FeishuClientError(f"send message failed: {result.get('msg', 'unknown')}")

        logger.info("feishu message sent to %s:%s", target_type, target_id)
        return result

    def send_test(self, target_type: str, target_id: str) -> dict[str, Any]:
        card = build_test_card()
        return self.send_card(target_type, target_id, card)


class FeishuClientError(RuntimeError):
    pass


def build_test_card() -> dict[str, Any]:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "✅ News Caught 连通性测试"},
            "template": "green",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "飞书推送通道已成功连接。\n此消息由 News Caught 系统发送。",
                },
            },
        ],
    }


def build_news_batch_card(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    lines = []
    for item in news_items[:20]:
        title = item.get("title", "")
        source = item.get("source_name", "")
        market = item.get("market", "").upper()
        lines.append(f"• **{title}**  _{source}_ | {market}")

    count = len(news_items)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📰 新闻聚合推送（{count} 条）"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines)},
            },
        ],
    }


def build_alert_card(
    symbol: str,
    display_name: str,
    price: float | None,
    change_percent: float | None,
    threshold: float | None,
) -> dict[str, Any]:
    direction = "📈" if (change_percent or 0) > 0 else "📉"
    color = "red" if (change_percent or 0) > 0 else "green"
    change_str = f"{change_percent:+.2f}%" if change_percent is not None else "N/A"
    price_str = f"{price:.2f}" if price is not None else "N/A"
    threshold_str = f"{threshold:.1f}%" if threshold is not None else "N/A"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{direction} 自选股异动 — {display_name}"},
            "template": color,
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**代码**\n{symbol}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**当前价格**\n{price_str}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**涨跌幅**\n{change_str}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**触发阈值**\n±{threshold_str}"}},
                ],
            },
        ],
    }


def build_analysis_card(
    news_title: str,
    top_pick: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    summary: str | None,
    risk_notes: str | None,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    sections.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**关联新闻**\n{news_title}"},
    })

    if top_pick:
        symbol = top_pick.get("symbol", "")
        company = top_pick.get("company_name", "")
        reason = top_pick.get("reason", "")
        sections.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**首选标的**：{company} ({symbol})\n{reason}",
            },
        })

    if candidates:
        candidate_lines = [
            f"• {c.get('company_name', '')} ({c.get('symbol', '')}) — {c.get('reason', '')}"
            for c in candidates[:5]
        ]
        sections.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**候选标的**\n" + "\n".join(candidate_lines)},
        })

    if summary:
        sections.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**摘要**\n{summary}"},
        })

    if risk_notes:
        sections.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**风险提示**\n{risk_notes}"},
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔍 LLM 标的分析"},
            "template": "purple",
        },
        "elements": sections,
    }
