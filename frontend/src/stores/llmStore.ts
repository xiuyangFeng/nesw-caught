import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { LLMConfigSummary, LLMConfigUpdateRequest } from '../types/api';

export const useLlmStore = defineStore('llmStore', () => {
  const config = ref<LLMConfigSummary | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const saveError = ref<string | null>(null);
  const saveSuccess = ref<string | null>(null);

  async function loadConfig() {
    loading.value = true;
    try {
      const response = await apiClient.getLlmConfig();
      config.value = response.data;
    } finally {
      loading.value = false;
    }
  }

  async function saveConfig(payload: LLMConfigUpdateRequest) {
    saving.value = true;
    saveError.value = null;
    saveSuccess.value = null;
    try {
      const response = await apiClient.saveLlmConfig(payload);
      config.value = response.data;
      saveSuccess.value = 'LLM 配置已保存';
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : '保存失败';
      throw error;
    } finally {
      saving.value = false;
    }
  }

  return {
    config,
    loading,
    saving,
    saveError,
    saveSuccess,
    loadConfig,
    saveConfig,
  };
});
