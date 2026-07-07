import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatSessions } from './useChatSessions';

const toastStore = {
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => toastStore,
}));

const getNewsDetail = vi.fn();

vi.mock('../api/client', () => ({
  apiClient: {
    getNewsDetail: (...args: unknown[]) => getNewsDetail(...args),
  },
}));

function createComposable(overrides: { defaultConfigId?: number | null; interruptStreaming?: () => void } = {}) {
  return useChatSessions({
    getDefaultConfigId: () => overrides.defaultConfigId ?? 7,
    interruptStreaming: overrides.interruptStreaming,
  });
}

describe('useChatSessions', () => {
  beforeEach(() => {
    // jsdom 环境下未开启持久化 localStorage，这里用内存实现替代
    const storage = new Map<string, string>();
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (key: string) => (storage.has(key) ? storage.get(key)! : null),
        setItem: (key: string, value: string) => {
          storage.set(key, String(value));
        },
        removeItem: (key: string) => {
          storage.delete(key);
        },
        clear: () => {
          storage.clear();
        },
      },
      configurable: true,
    });
    vi.clearAllMocks();
  });

  it('creates a default session when storage is empty', () => {
    const chat = createComposable();
    chat.initSessions();

    expect(chat.sessions.value).toHaveLength(1);
    const session = chat.sessions.value[0];
    expect(session.title).toBe('新对话');
    expect(session.newsId).toBeNull();
    expect(session.selectedConfigId).toBe(7);
    expect(session.messages).toHaveLength(1);
    expect(session.messages[0].role).toBe('assistant');
    expect(chat.activeSessionId.value).toBe(session.id);
  });

  it('persists sessions to localStorage and restores the active session', () => {
    const chat = createComposable();
    chat.initSessions();
    chat.createNewSession();
    const activeId = chat.activeSessionId.value;

    const restored = createComposable();
    restored.initSessions();

    expect(restored.sessions.value).toHaveLength(2);
    expect(restored.activeSessionId.value).toBe(activeId);
  });

  it('createSession applies title, greeting and newsId overrides', () => {
    const chat = createComposable();
    const session = chat.createSession({ title: '加载新闻中...', greeting: '自定义问候', newsId: 42 });

    expect(session.title).toBe('加载新闻中...');
    expect(session.newsId).toBe(42);
    expect(session.messages[0].content).toBe('自定义问候');
    expect(chat.activeSessionId.value).toBe(session.id);
  });

  it('selectSession interrupts streaming and switches the active session', () => {
    const interruptStreaming = vi.fn();
    const chat = createComposable({ interruptStreaming });
    chat.initSessions();
    const first = chat.sessions.value[0];
    chat.createNewSession();

    chat.selectSession(first.id);

    expect(interruptStreaming).toHaveBeenCalledTimes(1);
    expect(chat.activeSessionId.value).toBe(first.id);
  });

  it('deleteSession removes the session, picks a neighbour and shows a toast', () => {
    const interruptStreaming = vi.fn();
    const chat = createComposable({ interruptStreaming });
    chat.initSessions();
    chat.createNewSession();
    const [newer, older] = chat.sessions.value;

    chat.deleteSession(newer.id); // delete active session

    expect(interruptStreaming).toHaveBeenCalledTimes(1);
    expect(chat.sessions.value).toHaveLength(1);
    expect(chat.activeSessionId.value).toBe(older.id);
    expect(toastStore.showInfo).toHaveBeenCalledWith('会话已删除');
  });

  it('deleteSession recreates a default session when the last one is removed', () => {
    const chat = createComposable();
    chat.initSessions();
    const only = chat.sessions.value[0];

    chat.deleteSession(only.id);

    expect(chat.sessions.value).toHaveLength(1);
    expect(chat.sessions.value[0].id).not.toBe(only.id);
    expect(chat.sessions.value[0].title).toBe('新对话');
  });

  it('renameSession trims the title and ignores empty input', () => {
    const chat = createComposable();
    chat.initSessions();
    const session = chat.sessions.value[0];

    chat.renameSession(session.id, '  自定义标题  ');
    expect(session.title).toBe('自定义标题');

    chat.renameSession(session.id, '   ');
    expect(session.title).toBe('自定义标题');
  });

  it('openNewsSession reuses an existing session bound to the same news id', () => {
    const chat = createComposable();
    chat.initSessions();
    const newsSession = chat.createSession({ title: '新闻会话', newsId: 42 });
    chat.createNewSession();

    chat.openNewsSession(42);

    expect(chat.sessions.value).toHaveLength(3);
    expect(chat.activeSessionId.value).toBe(newsSession.id);
    expect(getNewsDetail).not.toHaveBeenCalled();
  });

  it('openNewsSession creates a news session and loads the news context', async () => {
    getNewsDetail.mockResolvedValue({ data: { title: '重磅新闻', summary: '摘要' } });
    const chat = createComposable();
    chat.initSessions();

    chat.openNewsSession(42);
    await vi.waitFor(() => {
      expect(getNewsDetail).toHaveBeenCalledWith(42);
    });

    const session = chat.currentSession.value!;
    expect(session.newsId).toBe(42);
    await vi.waitFor(() => {
      expect(session.title).toBe('新闻: 重磅新闻');
    });
    expect(session.newsDetail).toEqual({ title: '重磅新闻', summary: '摘要' });
  });

  it('shows an error toast when the news context cannot be loaded', async () => {
    getNewsDetail.mockResolvedValue({ data: null });
    const chat = createComposable();
    chat.initSessions();

    chat.openNewsSession(42);
    await vi.waitFor(() => {
      expect(toastStore.showError).toHaveBeenCalledWith('未找到对应的新闻详情');
    });
  });

  it('clearNewsContext resets news binding on the current session', () => {
    const chat = createComposable();
    chat.initSessions();
    const session = chat.currentSession.value!;
    session.newsId = 42;
    session.newsDetail = { title: 'x' } as any;
    session.title = '新闻: x';

    chat.clearNewsContext();

    expect(session.newsId).toBeNull();
    expect(session.newsDetail).toBeNull();
    expect(session.title).toBe('新对话');
  });
});
