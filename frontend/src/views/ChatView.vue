<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import { useLlmStore } from '../stores/llmStore';
import { useToastStore } from '../stores/toastStore';
import { parseMarkdown } from '../utils/markdown';
import type { LLMConfigSummary, NewsDetail } from '../types/api';

const route = useRoute();
const router = useRouter();
const llmStore = useLlmStore();
const toastStore = useToastStore();

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  failover?: {
    from_model: string;
    to_model: string;
    reason: string;
  };
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  newsId: number | null;
  newsDetail: NewsDetail | null;
  selectedConfigId: number | null;
  createdAt: number;
}

// sessions state
const sessions = ref<ChatSession[]>([]);
const activeSessionId = ref<string | null>(null);

// UI editing state
const editingSessionId = ref<string | null>(null);
const editingSessionTitle = ref('');
const titleInputRef = ref<HTMLInputElement[] | null>(null);

const inputMessage = ref('');
const isSending = ref(false);
const currentAbortController = ref<AbortController | null>(null);

// Get active sessions
const currentSession = computed(() => {
  return sessions.value.find((s) => s.id === activeSessionId.value) || null;
});

const messages = computed({
  get() {
    return currentSession.value?.messages || [];
  },
  set(val) {
    if (currentSession.value) {
      currentSession.value.messages = val;
    }
  }
});

const selectedConfigId = computed({
  get() {
    return currentSession.value?.selectedConfigId || defaultSelectedConfig.value?.id || null;
  },
  set(val) {
    if (currentSession.value) {
      currentSession.value.selectedConfigId = val;
      saveSessionsToStorage();
    }
  }
});

const activeConfigs = computed(() => {
  return llmStore.configs.filter((c) => c.is_active);
});

const defaultSelectedConfig = computed(() => {
  const def = activeConfigs.value.find((c) => c.is_default);
  if (def) return def;
  return activeConfigs.value[0] || null;
});

// Chat scroll control
const chatContainer = ref<HTMLDivElement | null>(null);
function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  });
}

// Storage helpers
function saveSessionsToStorage() {
  localStorage.setItem('news_caught_chat_sessions', JSON.stringify(sessions.value));
  if (activeSessionId.value) {
    localStorage.setItem('news_caught_active_session_id', activeSessionId.value);
  }
}

function loadSessionsFromStorage() {
  const stored = localStorage.getItem('news_caught_chat_sessions');
  const storedActive = localStorage.getItem('news_caught_active_session_id');
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

// Session CRUD
function createNewSession() {
  const id = Math.random().toString(36).substring(2, 9);
  const newSession: ChatSession = {
    id,
    title: '新对话',
    messages: [
      {
        role: 'assistant',
        content: '你好！我是 AI 智能助理。你可以向我发起日常咨询，或者基于特定新闻让我为您深度解析、总结要点或分析相关的个股影响。请在下方输入您的问题。',
      },
    ],
    newsId: null,
    newsDetail: null,
    selectedConfigId: defaultSelectedConfig.value?.id ?? null,
    createdAt: Date.now(),
  };
  sessions.value.unshift(newSession);
  activeSessionId.value = id;
  saveSessionsToStorage();
}

function selectSession(id: string) {
  // Abort any ongoing stream in previous session
  if (isSending.value) {
    stopGeneration();
  }
  activeSessionId.value = id;
  saveSessionsToStorage();
  scrollToBottom();
}

function deleteSession(id: string) {
  const idx = sessions.value.findIndex((s) => s.id === id);
  if (idx === -1) return;

  if (activeSessionId.value === id && isSending.value) {
    stopGeneration();
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

function startEditSessionTitle(session: ChatSession) {
  editingSessionId.value = session.id;
  editingSessionTitle.value = session.title;
  nextTick(() => {
    if (titleInputRef.value && titleInputRef.value[0]) {
      titleInputRef.value[0].focus();
    }
  });
}

function saveSessionTitle(id: string) {
  if (editingSessionId.value !== id) return;
  const session = sessions.value.find((s) => s.id === id);
  if (session) {
    const titleText = editingSessionTitle.value.trim();
    if (titleText) {
      session.title = titleText;
    }
  }
  editingSessionId.value = null;
  saveSessionsToStorage();
}

// Load News Context
async function loadNewsContextForSession(session: ChatSession, id: number) {
  try {
    const response = await apiClient.getNewsDetail(id);
    session.newsDetail = response.data;
    session.title = `新闻: ${response.data.title}`;
    saveSessionsToStorage();
  } catch (err) {
    console.error('Failed to load news detail for session context', err);
    toastStore.showError('加载关联新闻失败');
  }
}

// Quick preset prompts
const quickQuestions = [
  '请简述该新闻对相关股票的影响。',
  '该新闻主要表达了怎样的市场情绪？存在哪些风险？',
  '为我提炼这篇新闻的三个核心要点。',
];

function handleQuickQuestion(q: string) {
  inputMessage.value = q;
  void sendMessage();
}

function clearNewsContext() {
  if (currentSession.value) {
    currentSession.value.newsId = null;
    currentSession.value.newsDetail = null;
    currentSession.value.title = '新对话';
    saveSessionsToStorage();
  }
}

// Streaming abort
function stopGeneration() {
  if (currentAbortController.value) {
    currentAbortController.value.abort();
    currentAbortController.value = null;
  }
}

// Send Message
async function sendMessage() {
  const text = inputMessage.value.trim();
  if (!text || isSending.value || !currentSession.value) return;

  // Set session title automatically on first message
  if (currentSession.value.title === '新对话') {
    currentSession.value.title = text.length > 15 ? text.substring(0, 15) + '...' : text;
  }

  // Add user message
  messages.value.push({ role: 'user', content: text });
  inputMessage.value = '';
  isSending.value = true;
  scrollToBottom();

  // Create assistant placeholder
  const assistantMsg = ref<Message>({ role: 'assistant', content: '', isStreaming: true });
  messages.value.push(assistantMsg.value);
  scrollToBottom();

  // Build history array
  const history = messages.value
    .slice(0, -2) // Exclude current user message and placeholder
    .filter((m) => m.role !== 'system')
    .map((m) => ({ role: m.role, content: m.content }));

  currentAbortController.value = new AbortController();

  try {
    const response = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: text,
        history: history,
        news_id: currentSession.value.newsId,
        config_id: selectedConfigId.value,
        stream: true,
      }),
      signal: currentAbortController.value.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '请求大模型失败，请检查配置或连接。');
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('当前浏览器不支持读取 Stream。');
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.text) {
              assistantMsg.value.content += parsed.text;
              scrollToBottom();
            } else if (parsed.failover) {
              assistantMsg.value.failover = parsed.failover;
              toastStore.showWarning('由于主大模型异常，已自动为您无缝切换至备选模型！');
              scrollToBottom();
            } else if (parsed.error) {
              assistantMsg.value.content += `\n[错误: ${parsed.error}]`;
              scrollToBottom();
            }
          } catch {
            // Buffer chunk incomplete, skip
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      assistantMsg.value.content += '\n\n*(已中止生成)*';
      toastStore.showInfo('大模型流生成已中止');
    } else {
      assistantMsg.value.content = `【发送失败】 ${err.message || '网络连接发生异常'}`;
      toastStore.showError(err.message || '发送失败，请重试');
    }
  } finally {
    assistantMsg.value.isStreaming = false;
    isSending.value = false;
    currentAbortController.value = null;
    saveSessionsToStorage();
    scrollToBottom();
  }
}

// Auto scroll on updates
watch(() => messages.value, scrollToBottom, { deep: true });

onMounted(async () => {
  await llmStore.loadAllConfigs();
  loadSessionsFromStorage();

  // If no sessions, build default
  if (sessions.value.length === 0) {
    createNewSession();
  }

  // Handle news context routing
  const qNewsId = route.query.news_id;
  if (qNewsId) {
    const parsedId = parseInt(qNewsId as string, 10);
    if (!isNaN(parsedId)) {
      // Find if we already have a session for this news_id
      const existingSession = sessions.value.find((s) => s.newsId === parsedId);
      if (existingSession) {
        activeSessionId.value = existingSession.id;
      } else {
        // Create new session for the news
        const sessionId = Math.random().toString(36).substring(2, 9);
        const newSession: ChatSession = {
          id: sessionId,
          title: '加载新闻中...',
          messages: [
            {
              role: 'assistant',
              content: '你好！我已经将选定新闻的完整正文载入为上下文，请随时向我提问。',
            },
          ],
          newsId: parsedId,
          newsDetail: null,
          selectedConfigId: defaultSelectedConfig.value?.id ?? null,
          createdAt: Date.now(),
        };
        sessions.value.unshift(newSession);
        activeSessionId.value = sessionId;
        saveSessionsToStorage();
        void loadNewsContextForSession(newSession, parsedId);
      }
      // Replace URL query params
      void router.replace({ query: {} });
    }
  }
});
</script>

<template>
  <div class="grid grid-cols-[260px_1fr] gap-4 h-[calc(100vh-100px)]">
    <!-- Left Session sidebar -->
    <aside class="surface flex flex-col gap-3 rounded-[22px] p-4 overflow-hidden border border-border/40 bg-[rgba(10,17,28,0.4)]">
      <button
        class="w-full rounded-xl bg-[linear-gradient(135deg,#1768c2,#1e88e5)] hover:brightness-110 active:scale-[0.98] py-2.5 text-xs font-bold text-white shadow-md transition flex items-center justify-center gap-1.5 shrink-0"
        type="button"
        @click="createNewSession"
      >
        <span>➕</span> 新对话
      </button>

      <div class="flex-1 overflow-y-auto space-y-1 pr-0.5 min-h-0">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="group relative flex items-center justify-between rounded-xl px-3 py-2.5 text-xs transition cursor-pointer border select-none"
          :class="session.id === activeSessionId
            ? 'bg-white/[0.06] border-white/10 text-text font-semibold shadow-sm'
            : 'bg-transparent border-transparent text-text-faint hover:bg-white/[0.02] hover:text-text'"
          @click="selectSession(session.id)"
        >
          <!-- Session title editing -->
          <div class="flex-1 min-w-0 mr-1.5">
            <input
              v-if="editingSessionId === session.id"
              v-model="editingSessionTitle"
              class="w-full bg-field border border-border rounded px-1.5 py-0.5 text-xs text-text focus:outline-none focus:border-system"
              type="text"
              @blur="saveSessionTitle(session.id)"
              @keydown.enter="saveSessionTitle(session.id)"
              @click.stop
              ref="titleInputRef"
            />
            <span v-else class="truncate block">{{ session.title }}</span>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition shrink-0">
            <button
              class="hover:text-text p-0.5 transition"
              type="button"
              title="重命名"
              @click.stop="startEditSessionTitle(session)"
            >
              📝
            </button>
            <button
              class="hover:text-danger p-0.5 transition"
              type="button"
              title="删除会话"
              @click.stop="deleteSession(session.id)"
            >
              🗑️
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Right Chat Area -->
    <div class="grid gap-4 grid-rows-[auto_1fr_auto] min-w-0">
      <!-- Top header / Model selection -->
      <header class="surface flex flex-wrap items-center justify-between gap-4 rounded-[18px] px-4.5 py-3 border border-border/40">
        <div class="flex items-center gap-3">
          <span class="text-sm font-bold text-text">AI 对话助手</span>
          <div v-if="activeConfigs.length > 0" class="flex items-center gap-2">
            <span class="text-xs text-text-faint">使用模型:</span>
            <select
              v-model="selectedConfigId"
              class="rounded-lg border border-border bg-field px-2.5 py-1 text-xs text-text focus:outline-none focus:border-system"
            >
              <option v-for="cfg in activeConfigs" :key="cfg.id!" :value="cfg.id">
                {{ cfg.display_name || cfg.provider_name }} ({{ cfg.model_name }})
              </option>
            </select>
          </div>
          <span v-else class="text-xs text-danger">暂无可用模型，请先去配置</span>
        </div>
        <div class="text-[11px] uppercase tracking-wider text-muted font-mono hidden sm:block">
          Active AI Agent Workspace
        </div>
      </header>

      <!-- Chat viewport -->
      <div
        ref="chatContainer"
        class="surface flex flex-col gap-4 rounded-[22px] p-5 overflow-y-auto min-h-0 bg-[linear-gradient(180deg,rgba(12,19,30,0.4),rgba(8,14,23,0.4))] border border-border/40"
      >
        <!-- Linked news contextual banner -->
        <div
          v-if="currentSession && currentSession.newsDetail"
          class="relative flex flex-col md:flex-row items-start justify-between gap-4 rounded-xl border border-blue-500/20 bg-blue-500/5 p-4"
        >
          <div class="grid gap-1 min-w-0">
            <div class="flex items-center gap-2 text-xs font-semibold text-blue-400">
              <span class="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
              已关联新闻上下文
            </div>
            <h3 class="font-bold text-sm text-text truncate max-w-2xl mt-1">
              {{ currentSession.newsDetail.title }}
            </h3>
            <p class="text-xs text-text-faint line-clamp-2 mt-0.5">
              {{ currentSession.newsDetail.summary || '无摘要内容' }}
            </p>
          </div>
          <button
            class="rounded-lg px-2.5 py-1 text-xs font-semibold bg-white/[0.05] hover:bg-white/[0.1] text-text-faint hover:text-text transition shrink-0"
            type="button"
            @click="clearNewsContext"
          >
            清除关联
          </button>
        </div>

        <!-- Dialog bubbles -->
        <div class="flex flex-col gap-4 mt-2">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="flex flex-col max-w-[85%]"
            :class="msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'"
          >
            <!-- Label -->
            <span class="text-[10px] uppercase tracking-wider text-muted mb-1 font-mono">
              {{ msg.role === 'user' ? 'USER' : 'ASSISTANT' }}
            </span>
            <!-- Failover Alert Banner -->
            <div
              v-if="msg.role === 'assistant' && msg.failover"
              class="mb-2 p-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 backdrop-blur-md text-[11px] text-[#ffd175] flex items-center gap-2 select-text shadow-sm max-w-full"
            >
              <span class="animate-pulse">⚡</span>
              <span>
                <strong>故障接管</strong>：由于默认模型 <code>{{ msg.failover.from_model }}</code> 访问异常，已无缝切换至备选模型 <code>{{ msg.failover.to_model }}</code>。
              </span>
            </div>
            <!-- Bubble -->
            <div
              class="rounded-[18px] px-4 py-3 text-sm leading-relaxed shadow-sm select-text"
              :class="
                msg.role === 'user'
                  ? 'bg-[linear-gradient(135deg,#1768c2,#1e88e5)] text-white rounded-tr-sm'
                  : 'bg-white/[0.04] border border-border/60 text-text rounded-tl-sm markdown-body'
              "
            >
              <!-- Standard plain text for user messages -->
              <span v-if="msg.role === 'user'">{{ msg.content }}</span>
              <!-- Markdown parsing for LLM responses -->
              <div v-else v-html="parseMarkdown(msg.content)"></div>

              <span v-if="msg.isStreaming" class="inline-block w-1.5 h-4 ml-0.5 bg-system animate-pulse align-middle" />
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom controls -->
      <footer class="grid gap-3 shrink-0">
        <!-- Preset questions for news context -->
        <div v-if="currentSession && currentSession.newsDetail" class="flex flex-wrap gap-2">
          <button
            v-for="q in quickQuestions"
            :key="q"
            class="rounded-full border border-border/80 bg-white/[0.03] px-3.5 py-1.5 text-xs text-text-faint transition hover:border-system hover:bg-white/[0.06] hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
            type="button"
            :disabled="isSending"
            @click="handleQuickQuestion(q)"
          >
            {{ q }}
          </button>
        </div>

        <!-- Input box -->
        <form
          class="relative flex items-center gap-2 rounded-[20px] border border-border/80 bg-field p-2 focus-within:border-border"
          @submit.prevent="sendMessage"
        >
          <input
            v-model="inputMessage"
            class="flex-1 bg-transparent px-3 py-2 text-sm text-text focus:outline-none placeholder:text-muted"
            type="text"
            :placeholder="activeConfigs.length > 0 ? '向 AI 智能助理提问…' : '配置模型后即可在此输入提问'"
            :disabled="isSending || activeConfigs.length === 0"
          />
          <div class="flex items-center gap-2 shrink-0">
            <!-- Abort button -->
            <button
              v-if="isSending"
              class="rounded-xl bg-danger px-4 py-2 text-xs font-semibold text-white shadow-md transition hover:brightness-110 active:scale-95"
              type="button"
              @click="stopGeneration"
            >
              ■ 停止
            </button>
            <button
              class="rounded-xl bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2 text-xs font-semibold text-white shadow-md transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              type="submit"
              :disabled="!inputMessage.trim() || isSending || activeConfigs.length === 0"
            >
              发送
            </button>
          </div>
        </form>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.markdown-body :deep(p) {
  margin-bottom: 0.75rem;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul) {
  list-style-type: disc;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  padding-left: 1rem;
}
.markdown-body :deep(li) {
  margin-bottom: 0.25rem;
  color: var(--text-muted);
}
.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--text);
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.75rem;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 0.625rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.markdown-body :deep(th) {
  font-weight: 600;
  color: var(--text-faint);
  background-color: rgba(255, 255, 255, 0.02);
}
.markdown-body :deep(tr:hover) {
  background-color: rgba(255, 255, 255, 0.01);
}
.markdown-body :deep(code) {
  font-family: var(--font-mono, monospace);
}
</style>
