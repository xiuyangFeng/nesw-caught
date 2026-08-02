from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

from app.services import http_pool

logger = logging.getLogger(__name__)

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
TOKEN_REFRESH_BUFFER_SECONDS = 300


@dataclass
class FeishuToken:
    access_token: str
    expires_at: float


@dataclass(frozen=True)
class FeishuErrorClassification:
    retryable: bool
    refresh_token: bool = False
    reason: str = ""


@dataclass
class FeishuClient:
    app_id: str
    app_secret: str
    timeout: float = 10.0
    _token: FeishuToken | None = field(default=None, init=False, repr=False)

    def _get_http_client(self) -> httpx.Client:
        # 改用 http_pool 的共享 client，避免每个 FeishuClient 实例各自持有连接；
        # 生命周期由 http_pool.close_llm_client() 统一回收。
        return http_pool.get_feishu_client()

    def _get_tenant_access_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._token and now < self._token.expires_at - TOKEN_REFRESH_BUFFER_SECONDS:
            return self._token.access_token

        client = self._get_http_client()
        resp = client.post(
            FEISHU_TOKEN_URL,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            classification = classify_feishu_error(data)
            raise FeishuClientError(
                f"get token failed: {data.get('msg', 'unknown')}",
                retryable=classification.retryable,
                refresh_token=classification.refresh_token,
            )

        expire_seconds = data.get("expire", 7200)
        self._token = FeishuToken(
            access_token=data["tenant_access_token"],
            expires_at=now + expire_seconds,
        )
        return self._token.access_token

    def _send_card_once(
        self,
        *,
        target_type: str,
        target_id: str,
        card: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        receive_id_type = "chat_id" if target_type == "chat" else "open_id"
        client = self._get_http_client()
        resp = client.post(
            FEISHU_MESSAGE_URL,
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": target_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def send_card(
        self,
        target_type: str,
        target_id: str,
        card: dict[str, Any],
    ) -> dict[str, Any]:
        attempts = 0
        force_refresh = False
        while True:
            token = self._get_tenant_access_token(force_refresh=force_refresh)
            result = self._send_card_once(
                target_type=target_type,
                target_id=target_id,
                card=card,
                token=token,
            )
            classification = classify_feishu_error(result)
            if classification.refresh_token and attempts == 0:
                attempts += 1
                force_refresh = True
                continue
            if result.get("code") != 0:
                raise FeishuClientError(
                    f"send message failed: {result.get('msg', 'unknown')}",
                    retryable=classification.retryable,
                    refresh_token=classification.refresh_token,
                )
            logger.info("feishu message sent to %s:%s", target_type, target_id)
            return result

    def send_test(self, target_type: str, target_id: str) -> dict[str, Any]:
        card = build_test_card()
        return self.send_card(target_type, target_id, card)


class FeishuClientError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, refresh_token: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.refresh_token = refresh_token


def classify_feishu_error(error: Any) -> FeishuErrorClassification:
    code: int | None = None
    message = ""

    if isinstance(error, dict):
        raw_code = error.get("code")
        if isinstance(raw_code, int):
            code = raw_code
        elif isinstance(raw_code, str) and raw_code.isdigit():
            code = int(raw_code)
        raw_message = error.get("msg") or error.get("message")
        if isinstance(raw_message, str):
            message = raw_message.strip()
    elif isinstance(error, BaseException):
        message = str(error).strip()
    elif error is not None:
        message = str(error).strip()

    message_lower = message.lower()
    if code in {99991663, 99991664}:
        return FeishuErrorClassification(retryable=True, refresh_token=True, reason=message or f"code {code}")
    if "tenant_access_token" in message_lower and ("invalid" in message_lower or "expired" in message_lower):
        return FeishuErrorClassification(retryable=True, refresh_token=True, reason=message or "invalid token")
    if "access token" in message_lower and "invalid" in message_lower:
        return FeishuErrorClassification(retryable=True, refresh_token=True, reason=message or "invalid token")

    if code is not None and 50000 <= code < 60000:
        return FeishuErrorClassification(retryable=True, refresh_token=False, reason=message or f"code {code}")

    config_error_markers = (
        "app_id",
        "app secret",
        "app_secret",
        "permission",
        "forbidden",
        "unauthorized",
        "target_id",
    )
    if any(marker in message_lower for marker in config_error_markers):
        return FeishuErrorClassification(retryable=False, refresh_token=False, reason=message or "config error")

    if code in {40003, 40004, 40005, 40006}:
        return FeishuErrorClassification(retryable=False, refresh_token=False, reason=message or f"code {code}")

    return FeishuErrorClassification(retryable=False, refresh_token=False, reason=message or (f"code {code}" if code is not None else "unknown"))


@lru_cache(maxsize=32)
def get_shared_feishu_sender(app_id: str, app_secret: str, timeout: float = 10.0) -> FeishuClient:
    return FeishuClient(app_id=app_id, app_secret=app_secret, timeout=timeout)


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


def build_digest_card(digest: dict[str, Any]) -> dict[str, Any]:
    """构建每日盘前/盘后 AI 简报卡片，各 section 逐块渲染。"""
    title = digest.get("title") or "每日 AI 简报"
    generated_by = digest.get("generated_by")
    generated_at = digest.get("generated_at") or ""

    sections: list[dict[str, Any]] = []
    for section in digest.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_title = section.get("title", "")
        body = section.get("body", "")
        sections.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{section_title}**\n{body}"},
        })

    source_label = "LLM 生成" if generated_by == "llm" else "规则汇总"
    sections.append({
        "tag": "note",
        "elements": [
            {"tag": "lark_md", "content": f"来源：{source_label} · 生成时间(UTC)：{generated_at}"},
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🗞️ {title}"},
            "template": "wathet",
        },
        "elements": sections,
    }


def build_alert_digest_card(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """把免打扰 / 合并窗口内累积的多条自选股异动合并成一张摘要卡片。

    复用与单条 build_alert_card 一致的字段语义，只是折叠为列表，避免告警刷屏。
    """
    lines: list[str] = []
    for alert in alerts[:30]:
        symbol = alert.get("symbol", "")
        display_name = alert.get("display_name") or symbol
        change_percent = alert.get("change_percent")
        price = alert.get("price")
        direction = "📈" if (change_percent or 0) > 0 else "📉"
        change_str = f"{change_percent:+.2f}%" if change_percent is not None else "N/A"
        price_str = f"{price:.2f}" if price is not None else "N/A"
        lines.append(f"{direction} **{display_name}** ({symbol})  {change_str}  @ {price_str}")

    count = len(alerts)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🔔 自选股异动汇总（{count} 条）"},
            "template": "orange",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines) if lines else "（无异动明细）"},
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "已按告警治理策略合并，避免告警疲劳。"},
                ],
            },
        ],
    }


def build_sentiment_divergence_card(
    symbol: str,
    display_name: str,
    status: str,
    window_days: int | None,
    sentiment_avg: float | None,
    price_change_percent: float | None,
) -> dict[str, Any]:
    """情绪-价格背离提醒卡片。风格对齐 `build_alert_card`：同样是「标题态色 + 字段网格」。

    `bearish_divergence`：情绪偏多但价格走弱（红，风险提示）；
    `bullish_divergence`：情绪偏空但价格走强（绿，机会提示）。
    """
    is_bearish = status == "bearish_divergence"
    label = "情绪偏多、价格走弱" if is_bearish else "情绪偏空、价格走强"
    direction = "⚠️📉" if is_bearish else "⚠️📈"
    color = "red" if is_bearish else "green"
    sentiment_str = f"{sentiment_avg:+.2f}" if sentiment_avg is not None else "N/A"
    price_str = f"{price_change_percent:+.2f}%" if price_change_percent is not None else "N/A"
    window_str = f"近 {window_days} 天" if window_days is not None else "N/A"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{direction} 情绪-价格背离 — {display_name}"},
            "template": color,
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**代码**\n{symbol}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**观察窗口**\n{window_str}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**情绪均值**\n{sentiment_str}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**价格变动**\n{price_str}"}},
                ],
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"背离类型：{label}，建议结合基本面复核，非自动交易信号。"},
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
