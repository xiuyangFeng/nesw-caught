<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import { useLlmStore } from '../stores/llmStore';
import type { LLMConfigSummary, NewsDetail } from '../types/api';

const route = useRoute();
const router = useRouter();
const llmStore = useLlmStore();

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  isStreaming?: boolean;
}

const messages = ref<Message[]>([]);
const inputMessage = ref('');
const isSending = ref(false);
const selectedConfigId = ref<number | null>(null);

// 新闻上下文相关
const newsId = ref<number | null>(null);
const newsDetail = ref<NewsDetail | null>(null);
const loadingNews = ref(false);

const activeConfigs = computed(() => {
  return llmStore.configs.filter((c) => c.is_active);
});

const defaultSelectedConfig = computed(() => {
  const def = activeConfigs.value.find((c) => c.is_default);
  if (def) return def;
  return activeConfigs.value[0] || null;
});

// 对话框滚动控制
const chatContainer = ref<HTMLDivElement | null>(null);
function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  });
}

// 加载新闻详情
async function loadNewsContext(id: number) {
  loadingNews.value = true;
  try {
    const response = await apiClient.getNewsDetail(id);
    newsDetail.value = response.data;
  } catch (err) {
    console.error('Failed to load news detail for chat context', err);
  } finally {
    loadingNews.value = false;
  }
}

// 快捷追问选项
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
  newsId.value = null;
  newsDetail.value = null;
  // 清除 url 参数
  void router.replace({ query: {} });
}

// 发生聊天请求
async function sendMessage() {
  const text = inputMessage.value.trim();
  if (!text || isSending.value) return;

  // 添加用户消息
  messages.value.push({ role: 'user', content: text });
  inputMessage.value = '';
  isSending.value = true;
  scrollToBottom();

  // 预置助手流式消息
  const assistantMsg = ref<Message>({ role: 'assistant', content: '', isStreaming: true });
  messages.value.push(assistantMsg.value);
  scrollToBottom();

  // 构建历史消息列表 (不包含当前的 user 消息，后端会在请求端接收它)
  const history = messages.value
    .slice(0, -2) // 排除当前的 user 消息和刚刚添加的助手流式占位符
    .filter((m) => m.role !== 'system') // 过滤掉 system 消息，后端会单独生成
    .map((m) => ({ role: m.role, content: m.content }));

  try {
    const response = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: text,
        history: history,
        news_id: newsId.value,
        config_id: selectedConfigId.value,
        stream: true,
      }),
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
            } else if (parsed.error) {
              assistantMsg.value.content += `\n[错误: ${parsed.error}]`;
              scrollToBottom();
            }
          } catch {
            // 数据未接收完整，忽略
          }
        }
      }
    }
  } catch (err: any) {
    assistantMsg.value.content = `【发送失败】 ${err.message || '网络连接发生异常'}`;
  } finally {
    assistantMsg.value.isStreaming = false;
    isSending.value = false;
    scrollToBottom();
  }
}

// 自动滚动监测
watch(() => messages.value, scrollToBottom, { deep: true });

onMounted(async () => {
  await llmStore.loadAllConfigs();
  if (defaultSelectedConfig.value) {
    selectedConfigId.value = defaultSelectedConfig.value.id ?? null;
  }

  // 绑定新闻上下文
  const qNewsId = route.query.news_id;
  if (qNewsId) {
    const parsedId = parseInt(qNewsId as string, 10);
    if (!isNaN(parsedId)) {
      newsId.value = parsedId;
      void loadNewsContext(parsedId);
    }
  }

  // 首条欢迎信息
  messages.value.push({
    role: 'assistant',
    content: '你好！我是 AI 智能助理。你可以向我发起日常咨询，或者基于特定新闻让我为您深度解析、总结要点或分析相关的个股影响。请在下方输入您的问题。',
  });
});
</script>

<template>
  <div class="grid gap-4 h-[calc(100vh-100px)] grid-rows-[auto_1fr_auto]">
    <!-- 顶部状态栏及模型切换 -->
    <header class="surface flex flex-wrap items-center justify-between gap-4 rounded-[18px] px-4.5 py-3">
      <div class="flex items-center gap-3">
        <span class="text-sm font-bold text-text">AI 对话助手</span>
        <div v-if="activeConfigs.length > 0" class="flex items-center gap-2">
          <span class="text-xs text-text-faint">使用模型:</span>
          <select
            v-model="selectedConfigId"
            class="rounded-lg border border-border bg-field px-2.5 py-1 text-xs text-text focus:outline-none"
          >
            <option v-for="cfg in activeConfigs" :key="cfg.id!" :value="cfg.id">
              {{ cfg.display_name || cfg.provider_name }} ({{ cfg.model_name }})
            </option>
          </select>
        </div>
        <span v-else class="text-xs text-danger">暂无可用模型，请先去配置</span>
      </div>
      <div class="text-[11px] uppercase tracking-wider text-muted font-mono">
        Active AI Agent Workspace
      </div>
    </header>

    <!-- 聊天内容展示区域 -->
    <div
      ref="chatContainer"
      class="surface flex flex-col gap-4 rounded-[22px] p-5 overflow-y-auto min-h-0 bg-[linear-gradient(180deg,rgba(12,19,30,0.4),rgba(8,14,23,0.4))]"
    >
      <!-- 新闻上下文横幅 -->
      <div
        v-if="newsDetail"
        class="relative flex flex-col md:flex-row items-start justify-between gap-4 rounded-xl border border-blue-500/20 bg-blue-500/5 p-4"
      >
        <div class="grid gap-1 min-w-0">
          <div class="flex items-center gap-2 text-xs font-semibold text-blue-400">
            <span class="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
            已关联新闻上下文
          </div>
          <h3 class="font-bold text-sm text-text truncate max-w-2xl mt-1">
            {{ newsDetail.title }}
          </h3>
          <p class="text-xs text-text-faint line-clamp-2 mt-0.5">
            {{ newsDetail.summary || '无摘要内容' }}
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

      <!-- 对话列表 -->
      <div class="flex flex-col gap-4 mt-2">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="flex flex-col max-w-[85%]"
          :class="msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'"
        >
          <!-- 角色标识 -->
          <span class="text-[10px] uppercase tracking-wider text-muted mb-1 font-mono">
            {{ msg.role === 'user' ? 'USER' : 'ASSISTANT' }}
          </span>
          <!-- 消息气泡 -->
          <div
            class="rounded-[18px] px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-sm"
            :class="
              msg.role === 'user'
                ? 'bg-[linear-gradient(135deg,#1768c2,#1e88e5)] text-white rounded-tr-sm'
                : 'bg-white/[0.04] border border-border/60 text-text rounded-tl-sm'
            "
          >
            {{ msg.content }}
            <span v-if="msg.isStreaming" class="inline-block w-1.5 h-4 ml-0.5 bg-system animate-pulse align-middle" />
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入框与快捷提问 -->
    <footer class="grid gap-3">
      <!-- 快捷提问词列表 (仅在有关联新闻上下文时展示) -->
      <div v-if="newsDetail" class="flex flex-wrap gap-2">
        <button
          v-for="q in quickQuestions"
          :key="q"
          class="rounded-full border border-border/80 bg-white/[0.03] px-3.5 py-1.5 text-xs text-text-faint transition hover:border-system hover:bg-white/[0.06] hover:text-text"
          type="button"
          :disabled="isSending"
          @click="handleQuickQuestion(q)"
        >
          {{ q }}
        </button>
      </div>

      <!-- 输入框表单 -->
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
        <button
          class="rounded-xl bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2 text-xs font-semibold text-white shadow-md transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 shrink-0"
          type="submit"
          :disabled="!inputMessage.trim() || isSending || activeConfigs.length === 0"
        >
          {{ isSending ? '生成中…' : '发送' }}
        </button>
      </form>
    </footer>
  </div>
</template>
