import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatStream } from './useChatStream';
import type { ChatSession } from './useChatSessions';

const toastStore = {
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => toastStore,
}));

function buildSession(): ChatSession {
  return {
    id: 'abc',
    title: '新对话',
    messages: [{ role: 'assistant', content: '欢迎' }],
    newsId: null,
    newsDetail: null,
    selectedConfigId: 3,
    createdAt: Date.now(),
  };
}

function sseResponse(chunks: string[]) {
  let index = 0;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (index < chunks.length) {
            return { done: false, value: new TextEncoder().encode(chunks[index++]) };
          }
          return { done: true, value: undefined };
        },
      }),
    },
  };
}

function drainTypewriter(message: { isStreaming?: boolean }) {
  for (let i = 0; i < 200 && message.isStreaming; i += 1) {
    vi.advanceTimersByTime(30);
  }
}

describe('useChatStream', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('streams SSE text into an assistant message and persists the session', async () => {
    const session = buildSession();
    const persist = vi.fn();
    fetchMock.mockResolvedValue(
      sseResponse([
        'data: {"reasoning":"先识别问题，"}\n',
        'data: {"reasoning":"再组织答案"}\n',
        'data: {"text":"你好，"}\n',
        'data: {"text":"世界"}\n\n',
      ]),
    );

    const stream = useChatStream({
      getSession: () => session,
      getConfigId: () => 3,
      persist,
    });

    await stream.sendMessage('第一条提问');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/llm/chat');
    expect(JSON.parse(init.body)).toEqual({
      message: '第一条提问',
      history: [{ role: 'assistant', content: '欢迎' }],
      news_id: null,
      config_id: 3,
      stream: true,
    });

    // 自动以首条消息设置会话标题
    expect(session.title).toBe('第一条提问');
    expect(session.messages[1]).toEqual({ role: 'user', content: '第一条提问' });

    const assistant = session.messages[2];
    drainTypewriter(assistant);

    expect(assistant.content).toBe('你好，世界');
    expect(assistant.reasoning).toBe('先识别问题，再组织答案');
    expect(assistant.isStreaming).toBe(false);
    expect(stream.isSending.value).toBe(false);
    expect(persist).toHaveBeenCalled();
  });

  it('marks the message as failed and toasts on http error', async () => {
    const session = buildSession();
    const persist = vi.fn();
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: '模型配置无效' }),
    });

    const stream = useChatStream({
      getSession: () => session,
      getConfigId: () => null,
      persist,
    });

    await stream.sendMessage('测试');

    const assistant = session.messages[2];
    expect(assistant.content).toBe('【发送失败】 模型配置无效');
    expect(assistant.isStreaming).toBe(false);
    expect(toastStore.showError).toHaveBeenCalledWith('模型配置无效');
    expect(stream.isSending.value).toBe(false);
    expect(persist).toHaveBeenCalled();
  });

  it('appends an abort marker and toasts info when generation is aborted', async () => {
    const session = buildSession();
    const abortError = new Error('aborted');
    abortError.name = 'AbortError';
    fetchMock.mockRejectedValue(abortError);

    const stream = useChatStream({
      getSession: () => session,
      getConfigId: () => 3,
      persist: vi.fn(),
    });

    await stream.sendMessage('测试');

    const assistant = session.messages[2];
    drainTypewriter(assistant);

    expect(assistant.content).toContain('*(已中止生成)*');
    expect(assistant.isStreaming).toBe(false);
    expect(toastStore.showInfo).toHaveBeenCalledWith('大模型流生成已中止');
  });

  it('does nothing when there is no active session or empty text', async () => {
    const stream = useChatStream({
      getSession: () => null,
      getConfigId: () => 3,
      persist: vi.fn(),
    });

    await stream.sendMessage('测试');
    expect(fetchMock).not.toHaveBeenCalled();

    const session = buildSession();
    const streamWithSession = useChatStream({
      getSession: () => session,
      getConfigId: () => 3,
      persist: vi.fn(),
    });
    await streamWithSession.sendMessage('');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(session.messages).toHaveLength(1);
  });
});
