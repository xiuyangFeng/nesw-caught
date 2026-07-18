<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import LlmConfigForm from '../components/llm/LlmConfigForm.vue';
import LlmConfigList from '../components/llm/LlmConfigList.vue';
import TokenUsageConsole from '../components/llm/TokenUsageConsole.vue';
import type { TokenStats } from '../components/llm/types';
import { useLlmStore } from '../stores/llmStore';
import { useToastStore } from '../stores/toastStore';
import { apiClient } from '../api/client';
import type { LLMConfigSummary } from '../types/api';

const llmStore = useLlmStore();
const toastStore = useToastStore();

const stats = ref<TokenStats | null>(null);
const loadingStats = ref(false);

async function loadStats() {
  loadingStats.value = true;
  try {
    const res = await apiClient.getLlmStats();
    stats.value = res.data;
  } catch (err) {
    console.error('Failed to load stats', err);
  } finally {
    loadingStats.value = false;
  }
}

const hasActiveConfig = computed(() => llmStore.config?.configured === true);

async function submitConnectionTest() {
  if (!hasActiveConfig.value) {
    return;
  }
  try {
    await llmStore.testConnection();
    toastStore.showSuccess(llmStore.testSuccess || '连接测试成功！');
  } catch (err: any) {
    toastStore.showError(err.message || '连接测试失败');
  }
}

const configFormRef = ref<InstanceType<typeof LlmConfigForm> | null>(null);

function handleEdit(cfg: LLMConfigSummary) {
  configFormRef.value?.startEdit(cfg);
}

onMounted(() => {
  void llmStore.loadConfig();
  void llmStore.loadAllConfigs();
  void loadStats();
});
</script>

<template>
  <div class="grid gap-6">
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="page-title text-2xl font-bold tracking-tight">LLM Settings</h1>
        <p class="page-subtitle text-muted text-sm mt-1">配置和管理系统中多套大语言模型驱动，可快速切换或分配给聊天和翻译任务。</p>
      </div>
      <div v-if="hasActiveConfig" class="flex items-center gap-3">
        <button
          class="rounded-full bg-accent px-5 py-2 font-semibold text-bg transition hover:brightness-110 disabled:opacity-50"
          type="button"
          data-testid="test-connection-button"
          :disabled="llmStore.loading || llmStore.saving || llmStore.testingConnection"
          @click="submitConnectionTest"
        >
          {{ llmStore.testingConnection ? '正在测试默认模型连接…' : '测试默认连接' }}
        </button>
      </div>
    </header>

    <!-- Model usage token auditing dashboard -->
    <TokenUsageConsole v-if="stats" :stats="stats" :loading="loadingStats" @refresh="loadStats" />

    <div class="grid gap-6 lg:grid-cols-[1fr_380px]" data-role="llm-settings-grid">
      <!-- 左侧：模型列表 -->
      <div class="grid gap-4 self-start">
        <LlmConfigList @edit="handleEdit" />
      </div>

      <!-- 右侧：表单配置 -->
      <div class="grid gap-4 self-start">
        <LlmConfigForm ref="configFormRef" />
      </div>
    </div>
  </div>
</template>
