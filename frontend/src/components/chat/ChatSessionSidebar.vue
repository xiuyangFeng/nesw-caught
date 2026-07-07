<script setup lang="ts">
import { nextTick, ref } from 'vue';

import type { ChatSession } from '../../composables/useChatSessions';

defineProps<{
  sessions: ChatSession[];
  activeSessionId: string | null;
}>();

const emit = defineEmits<{
  (e: 'create'): void;
  (e: 'select', id: string): void;
  (e: 'delete', id: string): void;
  (e: 'rename', id: string, title: string): void;
}>();

// UI editing state
const editingSessionId = ref<string | null>(null);
const editingSessionTitle = ref('');
const titleInputRef = ref<HTMLInputElement[] | null>(null);

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
  emit('rename', id, editingSessionTitle.value);
  editingSessionId.value = null;
}
</script>

<template>
  <aside class="surface flex flex-col gap-3 rounded-[22px] p-4 overflow-hidden border border-border/40 bg-[rgba(10,17,28,0.4)]">
    <button
      class="w-full rounded-xl bg-[linear-gradient(135deg,#1768c2,#1e88e5)] hover:brightness-110 active:scale-[0.98] py-2.5 text-xs font-bold text-white shadow-md transition flex items-center justify-center gap-1.5 shrink-0"
      type="button"
      @click="emit('create')"
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
        @click="emit('select', session.id)"
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
            @click.stop="emit('delete', session.id)"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>
