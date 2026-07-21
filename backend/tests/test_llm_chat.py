import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.db.session import engine
from app.main import app


def _cleanup_llm_config_table() -> None:
    inspector = inspect(engine)
    if "llm_provider_config" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM llm_provider_config"))


async def mock_generate_text(*args, **kwargs):
    return "This is a mock response from async generate text."


async def mock_complete(*args, **kwargs):
    from app.services.llm_providers import CompletionResult

    return CompletionResult(content="This is a mock response from async generate text.")


async def mock_chat_stream(*args, **kwargs):
    yield ("token", "Hello")
    yield ("token", " ")
    yield ("token", "async")
    yield ("token", " ")
    yield ("token", "world")


def test_llm_multi_config_management_flow() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    # 1. 初始状态列表为空
    all_configs = client.get("/api/llm/config/all")
    assert all_configs.status_code == 200
    assert len(all_configs.json()) == 0

    # 2. 创建第一个配置 (默认会被设为 default 和 active)
    config_1 = client.post(
        "/api/llm/config",
        json={
            "id": None,
            "provider_name": "openai_compatible",
            "display_name": "DeepSeek v3",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-1",
            "is_active": True,
            "is_default": False, # 即使传 False,如果是第一个也会强设为 True
        },
    )
    assert config_1.status_code == 200
    data_1 = config_1.json()
    assert data_1["is_default"] is True
    assert data_1["is_active"] is True

    # 3. 创建第二个配置 (设为非默认，只设为 active)
    config_2 = client.post(
        "/api/llm/config",
        json={
            "id": None,
            "provider_name": "openai_compatible",
            "display_name": "GPT-4o",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4o",
            "api_key": "sk-test-2",
            "is_active": True,
            "is_default": False,
        },
    )
    assert config_2.status_code == 200
    data_2 = config_2.json()
    assert data_2["is_default"] is False
    assert data_2["is_active"] is True

    # 4. 获取全部配置
    all_configs_2 = client.get("/api/llm/config/all")
    assert all_configs_2.status_code == 200
    arr = all_configs_2.json()
    assert len(arr) == 2
    assert arr[0]["model_name"] == "deepseek-chat"
    assert arr[1]["model_name"] == "gpt-4o"

    # 5. 把第二个配置设为默认模型
    c2_id = data_2["id"]
    set_default_res = client.post(f"/api/llm/config/{c2_id}/default")
    assert set_default_res.status_code == 200
    assert set_default_res.json()["is_default"] is True

    # 6. 验证第一个配置已经不再是默认
    all_configs_3 = client.get("/api/llm/config/all")
    arr3 = all_configs_3.json()
    assert arr3[0]["is_default"] is False
    assert arr3[1]["is_default"] is True

    # 7. 更改第一个配置的启用状态为禁用 (is_active = False)
    c1_id = data_1["id"]
    active_res = client.post(f"/api/llm/config/{c1_id}/active?is_active=false")
    assert active_res.status_code == 200
    assert active_res.json()["is_active"] is False

    # 8. 删除第一个配置
    del_res = client.delete(f"/api/llm/config/{c1_id}")
    assert del_res.status_code == 204

    # 9. 确认只剩下一条
    all_configs_4 = client.get("/api/llm/config/all")
    assert len(all_configs_4.json()) == 1


@patch("app.services.llm_providers.AsyncOpenAICompatibleProvider.generate_text", new=mock_generate_text)
@patch("app.services.llm_providers.AsyncOpenAICompatibleProvider.chat_stream", new=mock_chat_stream)
@patch("app.services.llm_providers.AsyncOpenAICompatibleProvider.complete", new=mock_complete)
def test_llm_chat_flow() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    # 先创建一个默认的配置
    client.post(
        "/api/llm/config",
        json={
            "id": None,
            "provider_name": "openai_compatible",
            "display_name": "Default Model",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-active",
            "is_active": True,
            "is_default": True,
        },
    )

    # 1. 测试非流式对话 (stream=False)
    chat_non_stream = client.post(
        "/api/llm/chat",
        json={
            "message": "Hi, who are you?",
            "stream": False,
        },
    )
    assert chat_non_stream.status_code == 200
    assert "text" in chat_non_stream.json()
    assert chat_non_stream.json()["text"] == "This is a mock response from async generate text."

    # 2. 测试流式对话 (stream=True)
    chat_stream = client.post(
        "/api/llm/chat",
        json={
            "message": "Hi, who are you?",
            "stream": True,
        },
    )
    assert chat_stream.status_code == 200
    assert "text/event-stream" in chat_stream.headers["content-type"]

    # 读取流式响应内容并验证
    chunks = []
    for line in chat_stream.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if "text" in payload:
                chunks.append(payload["text"])

    response_text = "".join(chunks)
    assert response_text == "Hello async world"


def test_llm_chat_stream_disconnect_generator() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from app.api.routes.llm import chat_with_llm
    from app.schemas.llm import LLMChatRequest

    mock_session = MagicMock()
    payload = LLMChatRequest(
        message="Test message",
        history=[],
        stream=True
    )

    mock_request = MagicMock()
    # First call returns False, second returns True to simulate a client abort
    mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

    with patch("app.api.routes.llm.LLMProviderConfigRepository") as MockRepo, \
         patch("app.api.routes.llm.build_async_provider") as MockBuildProvider:

        mock_repo = MockRepo.return_value
        mock_config = MagicMock()
        mock_repo.get_default.return_value = mock_config

        mock_provider = MockBuildProvider.return_value

        async def mock_stream(*args, **kwargs):
            yield ("token", "Chunk1")
            yield ("token", "Chunk2")
            yield ("token", "Chunk3")

        mock_provider.chat_stream.side_effect = mock_stream

        async def _run_test():
            response = await chat_with_llm(payload=payload, request=mock_request, session=mock_session)
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(_run_test())

        # Since is_disconnected returned True on the second check, we should only get the first chunk
        assert len(chunks) == 1
        assert "Chunk1" in chunks[0]
        assert "Chunk2" not in "".join(chunks)


def test_llm_chat_resolves_context_off_event_loop_in_single_thread_hop() -> None:
    """回归 llm.py:196 的事件循环阻塞问题。

    chat_with_llm 进入流式/非流式分支前的同步 DB 读（config + news）必须
    收拢到一次 anyio.to_thread.run_sync 线程跳转里完成：
    1) 不能占用事件循环所在线程（否则撞上 SQLite 写锁会阻塞其它 async 请求/SSE）；
    2) 所有 DB 读要落在同一个 worker 线程上，不能多次线程往返。
    """
    from app.api.routes.llm import chat_with_llm
    from app.schemas.llm import LLMChatRequest

    main_thread_id = threading.get_ident()
    call_thread_ids: list[int] = []

    mock_session = MagicMock()
    payload = LLMChatRequest(message="Hi", history=[], stream=False, news_id=123)

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    with patch("app.api.routes.llm.LLMProviderConfigRepository") as MockConfigRepo, \
         patch("app.api.routes.llm.NewsRepository") as MockNewsRepo, \
         patch("app.api.routes.llm.build_async_provider") as MockBuildProvider:

        mock_config_repo = MockConfigRepo.return_value

        def _get_default(*args, **kwargs):
            call_thread_ids.append(threading.get_ident())
            return MagicMock()

        mock_config_repo.get_default.side_effect = _get_default

        mock_news_repo = MockNewsRepo.return_value

        def _get_news_by_id(news_id):
            call_thread_ids.append(threading.get_ident())
            return None  # 模拟关联新闻不存在，不应导致报错

        mock_news_repo.get_by_id.side_effect = _get_news_by_id

        mock_provider = MockBuildProvider.return_value
        mock_provider.complete = AsyncMock(side_effect=mock_complete)

        result = asyncio.run(
            chat_with_llm(payload=payload, request=mock_request, session=mock_session)
        )

    assert result["text"] == "This is a mock response from async generate text."
    # config + news 两次 DB 读都发生过
    assert len(call_thread_ids) == 2
    # 都不在事件循环线程（asyncio.run 所在的当前线程）上执行
    assert all(tid != main_thread_id for tid in call_thread_ids)
    # 两次读落在同一个 worker 线程，说明是一次线程跳转而非多次往返
    assert call_thread_ids[0] == call_thread_ids[1]


def test_llm_chat_missing_provider_returns_400() -> None:
    """provider 未配置时，错误分支仍走原错误码（400 + 原始文案）。"""
    _cleanup_llm_config_table()
    client = TestClient(app)

    response = client.post(
        "/api/llm/chat",
        json={"message": "Hello", "stream": False},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "LLM provider is not configured"


@patch("app.services.llm_providers.AsyncOpenAICompatibleProvider.complete", new=mock_complete)
def test_llm_chat_with_missing_news_id_still_succeeds() -> None:
    """news_id 指向不存在的新闻时不应报错，仍走原有正常响应路径。"""
    _cleanup_llm_config_table()
    client = TestClient(app)

    client.post(
        "/api/llm/config",
        json={
            "id": None,
            "provider_name": "openai_compatible",
            "display_name": "Default Model",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-active",
            "is_active": True,
            "is_default": True,
        },
    )

    response = client.post(
        "/api/llm/chat",
        json={"message": "Hi", "news_id": 999999, "stream": False},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "This is a mock response from async generate text."

