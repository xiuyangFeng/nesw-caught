import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_analysis_result import NewsAnalysisResult
from app.schemas.llm import LLMAnalysisCandidate, NewsAnalysisView


def _utc_now() -> datetime:
    return datetime.now(UTC)


class NewsAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_news_id(self, news_id: int) -> NewsAnalysisResult | None:
        stmt = select(NewsAnalysisResult).where(NewsAnalysisResult.news_id == news_id)
        return self.session.scalar(stmt)

    def upsert_success(
        self,
        *,
        news_id: int,
        provider_name: str,
        model_name: str,
        payload: dict[str, object],
    ) -> NewsAnalysisResult:
        item = self.get_by_news_id(news_id)
        if item is None:
            item = NewsAnalysisResult(news_id=news_id, provider_name=provider_name, model_name=model_name)
            self.session.add(item)

        top_pick = payload.get("top_pick") if isinstance(payload.get("top_pick"), dict) else None
        item.provider_name = provider_name
        item.model_name = model_name
        item.analysis_status = "success"
        item.top_pick_symbol = str(top_pick.get("symbol")) if top_pick and top_pick.get("symbol") else None
        item.top_pick_market = str(top_pick.get("market")) if top_pick and top_pick.get("market") else None
        item.top_pick_company_name = (
            str(top_pick.get("company_name")) if top_pick and top_pick.get("company_name") else None
        )
        item.top_pick_confidence = (
            str(top_pick.get("confidence")) if top_pick and top_pick.get("confidence") is not None else None
        )
        item.top_pick_reason = str(top_pick.get("reason")) if top_pick and top_pick.get("reason") else None
        item.summary = str(payload.get("summary")) if payload.get("summary") else None
        item.risk_notes = str(payload.get("risk_notes")) if payload.get("risk_notes") else None
        item.sentiment = str(payload.get("sentiment")) if payload.get("sentiment") else None
        item.context_limitations = (
            str(payload.get("context_limitations")) if payload.get("context_limitations") else None
        )
        item.analysis_error = None
        item.raw_response_json = json.dumps(payload, ensure_ascii=False)
        item.analyzed_at = _utc_now()
        self.session.flush()
        self.session.refresh(item)
        return item

    def upsert_error(
        self,
        *,
        news_id: int,
        provider_name: str,
        model_name: str,
        error: str,
    ) -> NewsAnalysisResult:
        item = self.get_by_news_id(news_id)
        if item is None:
            item = NewsAnalysisResult(news_id=news_id, provider_name=provider_name, model_name=model_name)
            self.session.add(item)

        item.provider_name = provider_name
        item.model_name = model_name
        item.analysis_status = "error"
        item.analysis_error = error
        item.analyzed_at = _utc_now()
        self.session.flush()
        self.session.refresh(item)
        return item


def to_analysis_view(item: NewsAnalysisResult | None) -> NewsAnalysisView | None:
    if item is None:
        return None

    parsed_payload: dict[str, object] = {}
    if item.raw_response_json:
        try:
            loaded = json.loads(item.raw_response_json)
            if isinstance(loaded, dict):
                parsed_payload = loaded
        except json.JSONDecodeError:
            parsed_payload = {}

    top_pick = parsed_payload.get("top_pick") if isinstance(parsed_payload.get("top_pick"), dict) else None
    candidate_rows = parsed_payload.get("candidates") if isinstance(parsed_payload.get("candidates"), list) else []

    return NewsAnalysisView(
        news_id=item.news_id,
        provider_name=item.provider_name,
        model_name=item.model_name,
        analysis_status=item.analysis_status,
        top_pick=LLMAnalysisCandidate.model_validate(top_pick) if top_pick else None,
        candidates=[
            LLMAnalysisCandidate.model_validate(candidate)
            for candidate in candidate_rows
            if isinstance(candidate, dict)
        ],
        summary=item.summary,
        risk_notes=item.risk_notes,
        sentiment=item.sentiment,
        context_limitations=item.context_limitations,
        analyzed_at=item.analyzed_at,
        analysis_error=item.analysis_error,
    )
