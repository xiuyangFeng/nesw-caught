<script setup lang="ts">
defineProps<{
  modelValue: string;
  isSending: boolean;
  hasActiveConfigs: boolean;
  showQuickQuestions: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'send'): void;
  (e: 'stop'): void;
  (e: 'quick', question: string): void;
}>();

// Quick preset prompts
const quickQuestions = [
  '请简述该新闻对相关股票的影响。',
  '该新闻主要表达了怎样的市场情绪？存在哪些风险？',
  '为我提炼这篇新闻的三个核心要点。',
];
</script>

<template>
  <footer class="grid gap-3 shrink-0">
    <!-- Preset questions for news context -->
    <div v-if="showQuickQuestions" class="flex flex-wrap gap-2">
      <button
        v-for="q in quickQuestions"
        :key="q"
        class="rounded-full border border-border/80 bg-white/[0.03] px-3.5 py-1.5 text-xs text-text-faint transition hover:border-system hover:bg-white/[0.06] hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
        type="button"
        :disabled="isSending"
        @click="emit('quick', q)"
      >
        {{ q }}
      </button>
    </div>

    <!-- Input box -->
    <form
      class="relative flex items-center gap-2 rounded-[20px] border border-border/80 bg-field p-2 focus-within:border-border"
      @submit.prevent="emit('send')"
    >
      <input
        :value="modelValue"
        class="flex-1 bg-transparent px-3 py-2 text-sm text-text focus:outline-none placeholder:text-muted"
        type="text"
        :placeholder="hasActiveConfigs ? '向 AI 智能助理提问…' : '配置模型后即可在此输入提问'"
        :disabled="isSending || !hasActiveConfigs"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      />
      <div class="flex items-center gap-2 shrink-0">
        <!-- Abort button -->
        <button
          v-if="isSending"
          class="rounded-xl bg-danger px-4 py-2 text-xs font-semibold text-white shadow-md transition hover:brightness-110 active:scale-95"
          type="button"
          @click="emit('stop')"
        >
          ■ 停止
        </button>
        <button
          class="rounded-xl bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2 text-xs font-semibold text-white shadow-md transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          type="submit"
          :disabled="!modelValue.trim() || isSending || !hasActiveConfigs"
        >
          发送
        </button>
      </div>
    </form>
  </footer>
</template>
