<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import LlmConfigModal from '../components/llm/LlmConfigModal.vue';
import LlmConfigList from '../components/llm/LlmConfigList.vue';
import TokenUsageConsole from '../components/llm/TokenUsageConsole.vue';
import type { TokenStats } from '../components/llm/types';
import { useLlmStore } from '../stores/llmStore';
import { useToastStore } from '../stores/toastStore';
import { apiClient } from '../api/client';
import type { LLMConfigSummary } from '../types/api';
import { logger } from '../utils/logger';

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
    logger.error('Failed to load stats', err);
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

const configModalOpen = ref(false);
const editingConfig = ref<LLMConfigSummary | null>(null);

function openNewConfig() {
  editingConfig.value = null;
  configModalOpen.value = true;
}

function handleEdit(cfg: LLMConfigSummary) {
  editingConfig.value = cfg;
  configModalOpen.value = true;
}

function closeConfigModal() {
  configModalOpen.value = false;
  editingConfig.value = null;
}

function handleConfigSaved() {
  closeConfigModal();
  void loadStats();
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

    <section
      class="surface relative overflow-hidden rounded-lg border border-border px-5 py-4"
      data-role="llm-config-launcher"
    >
      <div class="absolute inset-y-0 left-0 w-1 bg-[linear-gradient(180deg,var(--accent),var(--ai))]" />
      <div class="flex flex-wrap items-center justify-between gap-4 pl-2">
        <div class="max-w-2xl">
          <p class="label-mono text-[10px] text-accent">MODEL ACCESS</p>
          <h2 class="mt-1 text-lg font-bold text-text">需要接入或调整模型？</h2>
          <p class="mt-1 text-sm leading-6 text-text-soft">
            可在这里填写模型服务地址、API Key、价格与预算。配置表单只在需要时打开，不占用页面工作区。
          </p>
        </div>
        <button
          type="button"
          class="group inline-flex items-center gap-2 rounded-full border border-accent/45 bg-[var(--accent-soft)] px-4 py-2.5 text-sm font-semibold text-accent transition hover:-translate-y-0.5 hover:border-accent hover:shadow-glow"
          data-role="open-llm-config"
          @click="openNewConfig"
        >
          <span class="text-lg leading-none transition group-hover:rotate-90">＋</span>
          填写模型配置
        </button>
      </div>
    </section>

    <LlmConfigList @edit="handleEdit" />

    <LlmConfigModal
      :config="editingConfig"
      :open="configModalOpen"
      @close="closeConfigModal"
      @saved="handleConfigSaved"
    />
  </div>
</template>
