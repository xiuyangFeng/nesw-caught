<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import ChatSessionSidebar from '../components/chat/ChatSessionSidebar.vue';
import ChatMessageList from '../components/chat/ChatMessageList.vue';
import ChatInputBar from '../components/chat/ChatInputBar.vue';
import { useChatSessions } from '../composables/useChatSessions';
import { useChatStream } from '../composables/useChatStream';
import { useLlmStore } from '../stores/llmStore';

const route = useRoute();
const router = useRouter();
const llmStore = useLlmStore();

const activeConfigs = computed(() => {
  return llmStore.configs.filter((c) => c.is_active);
});

const defaultSelectedConfig = computed(() => {
  const def = activeConfigs.value.find((c) => c.is_default);
  if (def) return def;
  return activeConfigs.value[0] || null;
});

// 会话管理（创建/切换/持久化/新闻上下文）
const {
  sessions,
  activeSessionId,
  currentSession,
  saveSessionsToStorage,
  initSessions,
  createNewSession,
  selectSession,
  deleteSession,
  renameSession,
  openNewsSession,
  clearNewsContext,
} = useChatSessions({
  getDefaultConfigId: () => defaultSelectedConfig.value?.id ?? null,
  interruptStreaming: () => {
    if (isSending.value) {
      stopGeneration();
    }
  },
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

// 流式消息（SSE 请求 / 打字机渲染 / 中止）
const { isSending, stopGeneration, sendMessage } = useChatStream({
  getSession: () => currentSession.value,
  getConfigId: () => selectedConfigId.value,
  persist: saveSessionsToStorage,
});

const inputMessage = ref('');

const messages = computed(() => currentSession.value?.messages || []);

function handleSend() {
  const text = inputMessage.value.trim();
  if (!text || isSending.value || !currentSession.value) return;
  inputMessage.value = '';
  void sendMessage(text);
}

function handleQuickQuestion(q: string) {
  inputMessage.value = q;
  handleSend();
}

onMounted(async () => {
  await llmStore.loadAllConfigs();
  initSessions();

  // Handle news context routing
  const qNewsId = route.query.news_id;
  if (qNewsId) {
    const parsedId = parseInt(qNewsId as string, 10);
    if (!isNaN(parsedId)) {
      openNewsSession(parsedId);
      // Replace URL query params
      void router.replace({ query: {} });
    }
  }
});

onBeforeUnmount(() => {
  stopGeneration();
});
</script>

<template>
  <div
    class="grid h-[calc(100dvh-100px)] min-h-0 grid-cols-[260px_1fr] gap-4 overflow-hidden"
    data-role="chat-workspace"
  >
    <!-- Left Session sidebar -->
    <ChatSessionSidebar
      :sessions="sessions"
      :active-session-id="activeSessionId"
      @create="createNewSession"
      @select="selectSession"
      @delete="deleteSession"
      @rename="renameSession"
    />

    <!-- Right Chat Area -->
    <div
      class="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] gap-4 overflow-hidden"
      data-role="chat-main-column"
    >
      <!-- Top header / Model selection -->
      <header class="surface flex flex-wrap items-center justify-between gap-4 rounded-lg px-4 py-3">
        <div class="flex items-center gap-3">
          <!-- AI 头像徽标：唯一允许的渐变高光触点 -->
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-grad-ai text-sm font-bold text-bg shadow-glow-ai"
            aria-hidden="true"
          >✦</span>
          <span class="text-sm font-bold text-text">AI 对话助手</span>
          <div v-if="activeConfigs.length > 0" class="flex items-center gap-2">
            <span class="text-xs text-text-faint">使用模型</span>
            <select
              v-model="selectedConfigId"
              class="rounded-md border border-border bg-field px-2.5 py-1 text-xs text-text focus:outline-none focus:border-accent"
            >
              <option v-for="cfg in activeConfigs" :key="cfg.id!" :value="cfg.id">
                {{ cfg.display_name || cfg.provider_name }} ({{ cfg.model_name }})
              </option>
            </select>
          </div>
          <span v-else class="text-xs text-danger">暂无可用模型，请先去配置</span>
        </div>
        <span class="label-mono hidden sm:block">Active AI Agent Workspace</span>
      </header>

      <!-- Chat viewport container -->
      <ChatMessageList
        :messages="messages"
        :news-detail="currentSession?.newsDetail ?? null"
        @clear-context="clearNewsContext"
      />

      <!-- Bottom controls -->
      <ChatInputBar
        v-model="inputMessage"
        :is-sending="isSending"
        :has-active-configs="activeConfigs.length > 0"
        :show-quick-questions="Boolean(currentSession && currentSession.newsDetail)"
        @send="handleSend"
        @stop="stopGeneration"
        @quick="handleQuickQuestion"
      />
    </div>
  </div>
</template>
