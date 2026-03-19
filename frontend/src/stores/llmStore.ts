import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { LLMConfigSummary, LLMConfigUpdateRequest } from '../types/api';

export const useLlmStore = defineStore('llmStore', () => {
  const config = ref<LLMConfigSummary | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const testingConnection = ref(false);
  const loadError = ref<string | null>(null);
  const saveError = ref<string | null>(null);
  const saveSuccess = ref<string | null>(null);
  const testError = ref<string | null>(null);
  const testSuccess = ref<string | null>(null);

  async function loadConfig() {
    loading.value = true;
    loadError.value = null;
    try {
      const response = await apiClient.getLlmConfig();
      config.value = response.data;
    } catch (error) {
      loadError.value = error instanceof Error ? error.message : '加载失败';
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

  async function testConnection() {
    testingConnection.value = true;
    testError.value = null;
    testSuccess.value = null;
    try {
      const response = await apiClient.testLlmConnection();
      testSuccess.value = response.data.message;
    } catch (error) {
      testError.value = error instanceof Error ? error.message : '连接测试失败';
      throw error;
    } finally {
      testingConnection.value = false;
    }
  }

  return {
    config,
    loading,
    saving,
    testingConnection,
    loadError,
    saveError,
    saveSuccess,
    testError,
    testSuccess,
    loadConfig,
    saveConfig,
    testConnection,
  };
});
