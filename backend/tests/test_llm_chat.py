import json
from unittest.mock import patch
from sqlalchemy import inspect, text
from fastapi.testclient import TestClient

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


async def mock_chat_stream(*args, **kwargs):
    yield "Hello"
    yield " "
    yield "async"
    yield " "
    yield "world"


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
@patch("app.services.llm_providers.AsyncOpenAICompatibleProvider._request_completion", new=mock_generate_text)
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
            yield "Chunk1"
            yield "Chunk2"
            yield "Chunk3"

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

