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
  <div class="relative flex-1 min-h-0 flex flex-col">
    <div
      ref="chatContainer"
      class="surface flex flex-col gap-4 rounded-[22px] p-5 overflow-y-auto min-h-0 bg-[linear-gradient(180deg,rgba(12,19,30,0.4),rgba(8,14,23,0.4))] border border-border/40 flex-grow"
      @scroll="handleScroll"
    >
      <!-- Linked news contextual banner -->
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

    <!-- Float Scroll Bottom Button -->
    <transition name="fade-in">
      <button
        v-if="showScrollBottomBtn"
        class="absolute bottom-4 right-4 z-20 flex h-9 items-center gap-1.5 rounded-full border border-border/60 bg-[rgba(15,23,42,0.72)] px-3.5 text-xs text-[#90a2bb] hover:text-text backdrop-blur-md transition hover:bg-[rgba(30,41,59,0.92)] shadow-[0_4px_12px_rgba(0,0,0,0.3)] select-none cursor-pointer"
        type="button"
        @click="forceScrollToBottom"
      >
        <span>⬇</span> 回到底部
      </button>
    </transition>
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
