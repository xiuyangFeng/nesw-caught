import { computed, ref } from 'vue';

import { apiClient } from '../api/client';
import { useToastStore } from '../stores/toastStore';
import type { NewsDetail } from '../types/api';

export interface ChatMessageFailover {
  from_model: string;
  to_model: string;
  reason: string;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  /** 模型 API 实际返回的推理内容；不回传到后续对话历史。 */
  reasoning?: string;
  isStreaming?: boolean;
  failover?: ChatMessageFailover;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  newsId: number | null;
  newsDetail: NewsDetail | null;
  selectedConfigId: number | null;
  createdAt: number;
}

const SESSIONS_STORAGE_KEY = 'news_caught_chat_sessions';
const ACTIVE_SESSION_STORAGE_KEY = 'news_caught_active_session_id';

const DEFAULT_GREETING =
  '你好！我是 AI 智能助理。你可以向我发起日常咨询，或者基于特定新闻让我为您深度解析、总结要点或分析相关的个股影响。请在下方输入您的问题。';
const NEWS_GREETING = '你好！我已经将选定新闻的完整正文载入为上下文，请随时向我提问。';

export interface UseChatSessionsOptions {
  /** 新会话默认绑定的模型配置 id（通常来自 llmStore 的默认配置）。 */
  getDefaultConfigId: () => number | null;
  /** 切换/删除当前会话前调用，用于中止正在进行的流式生成。 */
  interruptStreaming?: () => void;
}

/**
 * 聊天会话管理 composable：负责会话的创建/切换/重命名/删除、
 * localStorage 持久化，以及新闻上下文的加载与清除。
 */
export function useChatSessions(options: UseChatSessionsOptions) {
  const toastStore = useToastStore();

  const sessions = ref<ChatSession[]>([]);
  const activeSessionId = ref<string | null>(null);

  const currentSession = computed(() => {
    return sessions.value.find((s) => s.id === activeSessionId.value) || null;
  });

  function saveSessionsToStorage() {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions.value));
    if (activeSessionId.value) {
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, activeSessionId.value);
    }
  }

  function loadSessionsFromStorage() {
    const stored = localStorage.getItem(SESSIONS_STORAGE_KEY);
    const storedActive = localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
    if (stored) {
      try {
        sessions.value = JSON.parse(stored);
        if (storedActive && sessions.value.some((s) => s.id === storedActive)) {
          activeSessionId.value = storedActive;
        } else if (sessions.value.length > 0) {
          activeSessionId.value = sessions.value[0].id;
        }
      } catch (err) {
        console.error('Failed to parse chat sessions', err);
      }
    }
  }

  /** 统一的会话创建入口：普通新对话与新闻上下文会话共用（消除重复创建逻辑）。 */
  function createSession(
    overrides: { title?: string; greeting?: string; newsId?: number | null } = {},
  ): ChatSession {
    const id = Math.random().toString(36).substring(2, 9);
    const newSession: ChatSession = {
      id,
      title: overrides.title ?? '新对话',
      messages: [
        {
          role: 'assistant',
          content: overrides.greeting ?? DEFAULT_GREETING,
        },
      ],
      newsId: overrides.newsId ?? null,
      newsDetail: null,
      selectedConfigId: options.getDefaultConfigId() ?? null,
      createdAt: Date.now(),
    };
    sessions.value.unshift(newSession);
    activeSessionId.value = id;
    saveSessionsToStorage();
    return newSession;
  }

  function createNewSession() {
    createSession();
  }

  /** 初始化：从 localStorage 恢复会话，若为空则建默认会话。 */
  function initSessions() {
    loadSessionsFromStorage();
    if (sessions.value.length === 0) {
      createNewSession();
    }
  }

  function selectSession(id: string) {
    // Abort any ongoing stream in previous session
    options.interruptStreaming?.();
    activeSessionId.value = id;
    saveSessionsToStorage();
  }

  function deleteSession(id: string) {
    const idx = sessions.value.findIndex((s) => s.id === id);
    if (idx === -1) return;

    if (activeSessionId.value === id) {
      options.interruptStreaming?.();
    }

    sessions.value.splice(idx, 1);
    if (sessions.value.length === 0) {
      createNewSession();
    } else if (activeSessionId.value === id) {
      activeSessionId.value = sessions.value[Math.min(idx, sessions.value.length - 1)].id;
    }
    saveSessionsToStorage();
    toastStore.showInfo('会话已删除');
  }

  function renameSession(id: string, title: string) {
    const session = sessions.value.find((s) => s.id === id);
    if (session) {
      const titleText = title.trim();
      if (titleText) {
        session.title = titleText;
      }
    }
    saveSessionsToStorage();
  }

  /** 拉取新闻详情并作为上下文附加到指定会话。 */
  async function loadNewsContextForSession(session: ChatSession, id: number) {
    try {
      const response = await apiClient.getNewsDetail(id);
      if (!response.data) {
        toastStore.showError('未找到对应的新闻详情');
        return;
      }
      session.newsDetail = response.data;
      session.title = `新闻: ${response.data.title}`;
      saveSessionsToStorage();
    } catch (err) {
      console.error('Failed to load news detail for session context', err);
      toastStore.showError('加载关联新闻失败');
    }
  }

  /** 打开指定新闻的会话：已有则切换，否则新建并异步加载新闻上下文。 */
  function openNewsSession(newsId: number) {
    const existingSession = sessions.value.find((s) => s.newsId === newsId);
    if (existingSession) {
      activeSessionId.value = existingSession.id;
      return;
    }
    const newSession = createSession({
      title: '加载新闻中...',
      greeting: NEWS_GREETING,
      newsId,
    });
    void loadNewsContextForSession(newSession, newsId);
  }

  function clearNewsContext() {
    if (currentSession.value) {
      currentSession.value.newsId = null;
      currentSession.value.newsDetail = null;
      currentSession.value.title = '新对话';
      saveSessionsToStorage();
    }
  }

  return {
    sessions,
    activeSessionId,
    currentSession,
    saveSessionsToStorage,
    loadSessionsFromStorage,
    initSessions,
    createSession,
    createNewSession,
    selectSession,
    deleteSession,
    renameSession,
    openNewsSession,
    clearNewsContext,
  };
}
