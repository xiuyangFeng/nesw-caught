from __future__ import annotations

from dataclasses import dataclass

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_analysis_repository import NewsAnalysisRepository, to_analysis_view
from app.repositories.news_repository import NewsRepository
from app.schemas.llm import NewsAnalysisView
from app.services.llm_providers import LLMProviderError, build_provider


class NewsAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalysisContext:
    prompt: str
    context_limitations: str | None


class NewsAnalysisService:
    def __init__(self, session) -> None:
        self.session = session
        self.news_repository = NewsRepository(session)
        self.analysis_repository = NewsAnalysisRepository(session)
        self.config_repository = LLMProviderConfigRepository(session)

    def get_latest(self, news_id: int) -> NewsAnalysisView | None:
        return to_analysis_view(self.analysis_repository.get_by_news_id(news_id))

    def analyze_news(self, news_id: int) -> NewsAnalysisView:
        news_item = self.news_repository.get_by_id(news_id)
        if news_item is None:
            raise NewsAnalysisError("news not found")

        config = self.config_repository.get_active()
        if config is None:
            raise NewsAnalysisError("llm provider is not configured")

        article = self.news_repository.get_article(news_id)
        context = self._build_context(news_item, article)

        try:
            payload = build_provider(config).analyze_json(
                prompt=context.prompt,
                title=news_item.title,
                summary=news_item.summary,
                market=news_item.market,
            )
        except LLMProviderError as exc:
            self.analysis_repository.upsert_error(
                news_id=news_id,
                provider_name=config.provider_name,
                model_name=config.model_name,
                error=str(exc),
            )
            # 失败记录必须在异常上抛（触发请求级 rollback）之前提交落库。
            self.session.commit()
            raise NewsAnalysisError(str(exc)) from exc

        if not isinstance(payload, dict):
            self.analysis_repository.upsert_error(
                news_id=news_id,
                provider_name=config.provider_name,
                model_name=config.model_name,
                error="llm provider returned invalid analysis payload",
            )
            # 失败记录必须在异常上抛（触发请求级 rollback）之前提交落库。
            self.session.commit()
            raise NewsAnalysisError("llm provider returned invalid analysis payload")

        normalized_payload = dict(payload)
        normalized_payload["context_limitations"] = (
            str(normalized_payload.get("context_limitations"))
            if normalized_payload.get("context_limitations")
            else context.context_limitations
        )

        item = self.analysis_repository.upsert_success(
            news_id=news_id,
            provider_name=config.provider_name,
            model_name=config.model_name,
            payload=normalized_payload,
        )
        return to_analysis_view(item)

    def _build_context(self, news_item: NewsItem, article: ArticleContent | None) -> AnalysisContext:
        body = article.content_text.strip() if article and article.content_text else None
        context_limitations = None if body else "article body missing"
        prompt = "\n".join(
            [
                f"Title: {news_item.title}",
                f"Summary: {news_item.summary or ''}",
                f"Market: {news_item.market}",
                f"Source: {news_item.source_name}",
                f"Published At: {news_item.published_at.isoformat() if news_item.published_at else ''}",
                f"Body: {body or ''}",
                (
                    "Return the single most important listed equity read-through in top_pick, "
                    "candidate equities in candidates, concise summary, risk_notes, sentiment, and context_limitations."
                ),
            ]
        )
        return AnalysisContext(prompt=prompt, context_limitations=context_limitations)
