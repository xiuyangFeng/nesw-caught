from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.llm_provider_config import LLMProviderConfig
from app.models.llm_token_usage import LLMTokenUsage
from app.services.llm_providers import OpenAICompatibleProvider, log_token_usage


def test_log_token_usage() -> None:
    with SessionLocal() as session:
        session.query(LLMTokenUsage).delete()
        session.commit()

    log_token_usage(
        model_name="deepseek-chat",
        prompt_tokens=100,
        completion_tokens=200,
        operation_type="chat"
    )

    with SessionLocal() as session:
        usage = session.scalar(select(LLMTokenUsage).where(LLMTokenUsage.model_name == "deepseek-chat"))
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 200
        assert usage.total_tokens == 300
        assert usage.operation_type == "chat"


def test_llm_stats_api() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        session.query(LLMTokenUsage).delete()
        session.commit()

    log_token_usage(
        model_name="gpt-4o",
        prompt_tokens=50,
        completion_tokens=100,
        operation_type="analysis"
    )

    res = client.get("/api/llm/stats")
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert data["overall"]["total_tokens"] == 150
    assert len(data["models"]) == 1
    assert data["models"][0]["model_name"] == "gpt-4o"
    assert data["models"][0]["total_tokens"] == 150
    assert len(data["operations"]) == 1
    assert data["operations"][0]["operation_type"] == "analysis"


def test_llm_provider_failover() -> None:
    from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
    session = SessionLocal()
    try:
        repo = LLMProviderConfigRepository(session)
        session.query(LLMProviderConfig).delete()
        session.commit()

        c1 = repo.upsert_config(
            provider_name="openai_compatible",
            display_name="Primary",
            base_url="https://api.primary.com/v1",
            model_name="primary-model",
            api_key="sk-primary",
            is_active=True,
            is_default=True,
        )

        repo.upsert_config(
            provider_name="openai_compatible",
            display_name="Backup",
            base_url="https://api.backup.com/v1",
            model_name="backup-model",
            api_key="sk-backup",
            is_active=True,
            is_default=False,
        )
        # repository 只 flush：failover 会用独立会话读取备份配置，需先提交。
        session.commit()

        provider = OpenAICompatibleProvider(c1)

        with patch("httpx.Client.post") as mock_post:
            # First call (primary) raises bad status code
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 502
            mock_response_fail.json.return_value = {"error": {"message": "Bad gateway"}}

            # Second call (backup) succeeds
            mock_response_ok = MagicMock()
            mock_response_ok.status_code = 200
            mock_response_ok.json.return_value = {
                "choices": [{"message": {"content": "Succeeded on backup"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

            mock_post.side_effect = [mock_response_fail, mock_response_ok]

            result = provider.complete(
                messages=[{"role": "user", "content": "ping"}],
                operation_type="chat"
            )

            assert result.content == "Succeeded on backup"
            assert mock_post.call_count == 2
            assert provider.failover_triggered is not None
            assert provider.failover_triggered["from_model"] == "primary-model"
            assert provider.failover_triggered["to_model"] == "backup-model"
            # Structured result carries the same failover info for callers
            assert result.failover == provider.failover_triggered
    finally:
        session.close()


def test_llm_ping_api() -> None:
    client = TestClient(app)
    from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
    session = SessionLocal()
    try:
        repo = LLMProviderConfigRepository(session)
        session.query(LLMProviderConfig).delete()
        session.commit()

        c = repo.upsert_config(
            provider_name="openai_compatible",
            display_name="PingTest",
            base_url="https://api.pingtest.com/v1",
            model_name="ping-model",
            api_key="sk-ping",
            is_active=True,
            is_default=True,
        )
        # repository 只 flush：ping API 使用独立请求会话，需先提交。
        session.commit()

        with patch("app.services.llm_providers.OpenAICompatibleProvider.generate_text") as mock_gen:
            mock_gen.return_value = "pong"

            res = client.post(f"/api/llm/config/{c.id}/ping")
            assert res.status_code == 200
            data = res.json()
            assert data["provider_name"] == "openai_compatible"
            assert data["model_name"] == "ping-model"
            assert "latency_ms" in data
            assert data["latency_ms"] >= 0
    finally:
        session.close()


def test_llm_stats_daily_trend() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        session.query(LLMTokenUsage).delete()
        session.commit()

        usage = LLMTokenUsage(
            model_name="deepseek-chat",
            prompt_tokens=200,
            completion_tokens=300,
            total_tokens=500,
            operation_type="chat"
        )
        session.add(usage)
        session.commit()

    res = client.get("/api/llm/stats")
    assert res.status_code == 200
    data = res.json()
    assert "daily" in data
    assert len(data["daily"]) >= 1
    assert data["daily"][0]["total_tokens"] == 500
    assert data["daily"][0]["prompt_tokens"] == 200
    assert data["daily"][0]["completion_tokens"] == 300


def test_llm_chat_failover_sse() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from app.api.routes.llm import chat_with_llm
    from app.schemas.llm import LLMChatRequest

    mock_session = MagicMock()
    payload = LLMChatRequest(
        message="Hello",
        history=[],
        stream=True
    )

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    with patch("app.api.routes.llm.LLMProviderConfigRepository") as MockRepo, \
         patch("app.api.routes.llm.build_async_provider") as MockBuildProvider:

        mock_repo = MockRepo.return_value
        mock_config = MagicMock()
        mock_repo.get_default.return_value = mock_config

        mock_provider = MockBuildProvider.return_value

        async def mock_stream(*args, **kwargs):
            yield ("failover", {"from_model": "gpt-4o", "to_model": "deepseek-chat", "reason": "HTTP 502"})
            yield ("token", "Hello")

        mock_provider.chat_stream.side_effect = mock_stream

        async def _run():
            response = await chat_with_llm(payload=payload, request=mock_request, session=mock_session)
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(_run())
        assert len(chunks) == 2
        assert "failover" in chunks[0]
        assert "gpt-4o" in chunks[0]
        assert "deepseek-chat" in chunks[0]
        assert "text" in chunks[1]
        assert "Hello" in chunks[1]
