<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

import { parseMarkdown } from '../../utils/markdown';
import type { ChatMessage } from '../../composables/useChatSessions';
import type { NewsDetail } from '../../types/api';

const props = defineProps<{
  messages: ChatMessage[];
  newsDetail: NewsDetail | null;
}>();

const emit = defineEmits<{
  (e: 'clear-context'): void;
}>();

// Chat scroll control
const chatContainer = ref<HTMLDivElement | null>(null);
const shouldAutoScroll = ref(true);
const showScrollBottomBtn = ref(false);
let isAutoScrolling = false;

function scrollToBottom() {
  if (!shouldAutoScroll.value) return;
  nextTick(() => {
    if (chatContainer.value) {
      isAutoScrolling = true;
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
      setTimeout(() => {
        isAutoScrolling = false;
      }, 50);
    }
  });
}

function forceScrollToBottom() {
  shouldAutoScroll.value = true;
  showScrollBottomBtn.value = false;
  nextTick(() => {
    if (chatContainer.value) {
      isAutoScrolling = true;
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
      setTimeout(() => {
        isAutoScrolling = false;
      }, 50);
    }
  });
}

function handleScroll() {
  if (!chatContainer.value) return;
  const { scrollTop, scrollHeight, clientHeight } = chatContainer.value;
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
  if (isAtBottom) {
    shouldAutoScroll.value = true;
    showScrollBottomBtn.value = false;
  } else {
    if (!isAutoScrolling) {
      shouldAutoScroll.value = false;
      showScrollBottomBtn.value = true;
    }
  }
}

// Auto scroll on updates (covers streaming appends and session switches)
watch(() => props.messages, scrollToBottom, { deep: true });
</script>

<template>
  <div class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
    <div
      ref="chatContainer"
      class="chat-scroll-viewport surface flex min-h-0 flex-grow flex-col gap-4 overflow-y-auto overscroll-contain rounded-lg p-5"
      data-role="chat-message-viewport"
      @scroll="handleScroll"
    >
      <!-- Linked news contextual banner -->
      <div
        v-if="newsDetail"
        class="relative flex flex-col md:flex-row items-start justify-between gap-4 rounded-md border border-border bg-[var(--accent-soft)] p-4"
      >
        <div class="grid gap-1 min-w-0">
          <div class="flex items-center gap-2 text-xs font-semibold text-accent">
            <span class="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
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
          class="rounded-md px-2.5 py-1 text-xs font-semibold bg-panel-strong hover:bg-bg-elevated text-text-faint hover:text-text transition shrink-0"
          type="button"
          @click="emit('clear-context')"
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
          <span class="label-mono mb-1 flex items-center gap-1.5">
            <span v-if="msg.role !== 'user'" class="text-ai">✦</span>
            {{ msg.role === 'user' ? 'USER' : 'ASSISTANT' }}
          </span>
          <!-- Failover Alert Banner -->
          <div
            v-if="msg.role === 'assistant' && msg.failover"
            class="mb-2 p-2.5 rounded-md border border-border bg-[var(--warning-soft)] text-[11px] text-warning flex items-center gap-2 select-text max-w-full"
          >
            <span class="animate-pulse">⚡</span>
            <span>
              <strong>故障接管</strong>：由于默认模型 <code>{{ msg.failover.from_model }}</code> 访问异常，已无缝切换至备选模型 <code>{{ msg.failover.to_model }}</code>。
            </span>
          </div>
          <!-- Provider-returned reasoning stays visually secondary to the final answer. -->
          <details
            v-if="msg.role === 'assistant' && msg.reasoning"
            class="reasoning-panel mb-2 w-full max-w-3xl overflow-hidden rounded-md border border-border bg-panel/70"
            :open="msg.isStreaming"
            data-testid="reasoning-panel"
          >
            <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-xs text-text-faint">
              <span class="flex items-center gap-2 font-semibold">
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  :class="msg.isStreaming ? 'animate-pulse bg-accent' : 'bg-success'"
                />
                {{ msg.isStreaming ? '推理中' : '模型推理过程' }}
              </span>
              <span class="label-mono">REASONING TRACE</span>
            </summary>
            <div class="reasoning-content border-t border-border px-3 py-3 text-xs leading-6 text-text-faint whitespace-pre-wrap">
              {{ msg.reasoning }}
            </div>
          </details>
          <!-- Bubble -->
          <div
            class="relative rounded-md px-4 py-3 text-sm leading-relaxed select-text"
            :class="
              msg.role === 'user'
                ? 'bg-panel-strong text-text rounded-tr-sm'
                : 'ai-bubble bg-panel border border-border text-text rounded-tl-sm markdown-body'
            "
          >
            <!-- Standard plain text for user messages -->
            <span v-if="msg.role === 'user'">{{ msg.content }}</span>
            <!-- Markdown parsing for LLM responses -->
            <div v-else-if="msg.content" v-html="parseMarkdown(msg.content)"></div>
            <span v-else class="text-text-faint">正在组织最终回答…</span>

            <span v-if="msg.isStreaming" class="inline-block w-1.5 h-4 ml-0.5 bg-accent animate-pulse align-middle" />
          </div>
        </div>
      </div>
    </div>

    <!-- Float Scroll Bottom Button -->
    <transition name="fade-in">
      <button
        v-if="showScrollBottomBtn"
        class="absolute bottom-4 right-4 z-20 flex h-9 items-center gap-1.5 rounded-full border border-border bg-panel-strong px-3.5 text-xs text-text-faint hover:text-text transition hover:bg-bg-elevated select-none cursor-pointer"
        type="button"
        @click="forceScrollToBottom"
      >
        <span class="text-accent">↓</span> 回到底部
      </button>
    </transition>
  </div>
</template>

<style scoped>
/* AI 助手气泡：左侧青紫渐变强调条（克制，不整屏发光） */
.ai-bubble::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  border-radius: 2px;
  background: var(--grad-ai);
}

.reasoning-panel summary::-webkit-details-marker {
  display: none;
}

.reasoning-panel[open] summary {
  background: color-mix(in srgb, var(--panel-strong) 72%, transparent);
}

.reasoning-content {
  background-image: linear-gradient(90deg, color-mix(in srgb, var(--accent) 12%, transparent) 1px, transparent 1px);
  background-size: 24px 100%;
}

.chat-scroll-viewport {
  scrollbar-gutter: stable;
}

.markdown-body :deep(p) {
  margin-bottom: 0.75rem;
  color: var(--text-soft);
  line-height: 1.7;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  padding-left: 1.1rem;
}
.markdown-body :deep(ul) {
  list-style-type: disc;
}
.markdown-body :deep(ol) {
  list-style-type: decimal;
}
.markdown-body :deep(li) {
  margin-bottom: 0.25rem;
  color: var(--text-soft);
}
.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--text);
}
.markdown-body :deep(a) {
  color: var(--system);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.75rem;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 0.5rem 0.85rem;
  border-bottom: 1px solid var(--border);
}
.markdown-body :deep(th) {
  font-weight: 600;
  color: var(--text-faint);
  background: var(--panel-strong);
}
.markdown-body :deep(tr:hover) {
  background: var(--interactive-hover);
}
/* 代码等宽；行内码收成青色小片，代码块保持素净等宽 */
.markdown-body :deep(code) {
  font-family: var(--font-mono, monospace);
}
.markdown-body :deep(:not(pre) > code) {
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
}
.markdown-body :deep(pre) {
  font-family: var(--font-mono, monospace);
  color: var(--text-soft);
}
.markdown-body :deep(.code-block-wrapper) {
  background: var(--panel-stronger);
}

/* 渐显动画 */
.fade-in-enter-active,
.fade-in-leave-active {
  transition: opacity 0.2s ease;
}
.fade-in-enter-from,
.fade-in-leave-to {
  opacity: 0;
}
</style>
