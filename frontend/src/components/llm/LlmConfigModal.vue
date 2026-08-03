<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { LLMConfigSummary } from '../../types/api';
import LlmConfigForm from './LlmConfigForm.vue';

const props = defineProps<{
  open: boolean;
  config: LLMConfigSummary | null;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
}>();

const formRef = ref<InstanceType<typeof LlmConfigForm> | null>(null);

watch(
  () => [props.open, props.config] as const,
  async ([open, config]) => {
    if (!open) return;
    await nextTick();
    if (config) {
      formRef.value?.startEdit(config);
    } else {
      formRef.value?.resetForm();
    }
  },
  { immediate: true },
);

function handleKeydown(event: KeyboardEvent) {
  if (props.open && event.key === 'Escape') {
    emit('close');
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-[color-mix(in_srgb,var(--bg)_78%,transparent)] px-4 py-6 backdrop-blur-sm"
    aria-modal="true"
    data-role="llm-config-modal"
    role="dialog"
    aria-labelledby="llm-config-modal-title"
    @click.self="emit('close')"
  >
    <section class="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-[26px] border border-border bg-panel shadow-shell">
      <header class="flex items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
        <div>
          <p class="label-mono text-[10px] text-accent">MODEL CONNECTION</p>
          <h2 id="llm-config-modal-title" class="mt-1 text-xl font-bold text-text">
            {{ config ? '编辑模型配置' : '填写模型配置' }}
          </h2>
          <p class="mt-1 text-sm text-text-soft">
            {{ config ? `正在修改 ${config.display_name || config.model_name}` : '选择服务预设或填写自定义兼容接口，保存后窗口会自动关闭。' }}
          </p>
        </div>
        <button
          type="button"
          class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border text-lg text-text-faint transition hover:border-accent hover:text-text"
          aria-label="关闭模型配置窗口"
          data-role="close-llm-config"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <div class="overflow-y-auto px-5 py-5 sm:px-6">
        <LlmConfigForm ref="formRef" @cancel="emit('close')" @saved="emit('saved')" />
      </div>
    </section>
  </div>
</template>
