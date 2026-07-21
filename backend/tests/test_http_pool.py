from __future__ import annotations

import httpx

from app.services import http_pool


def test_get_feishu_client_returns_shared_singleton():
    """飞书专用共享 client 应懒加载且跨调用复用同一实例，避免每次请求新建连接。"""
    http_pool.close_llm_client()
    try:
        client1 = http_pool.get_feishu_client()
        client2 = http_pool.get_feishu_client()

        assert isinstance(client1, httpx.Client)
        assert client1 is client2
    finally:
        http_pool.close_llm_client()


def test_close_llm_client_also_closes_feishu_client():
    """close_llm_client() 是进程关闭时统一回收入口，飞书 client 也要跟随回收。"""
    client = http_pool.get_feishu_client()
    assert client.is_closed is False

    http_pool.close_llm_client()

    assert client.is_closed is True
    # 关闭后再次获取应得到一个全新的、未关闭的 client（懒重建）
    new_client = http_pool.get_feishu_client()
    assert new_client is not client
    assert new_client.is_closed is False

    http_pool.close_llm_client()
