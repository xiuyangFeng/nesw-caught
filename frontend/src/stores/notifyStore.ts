import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { FeishuNotifyConfig, FeishuNotifyConfigUpdate, FeishuTestResult } from '../types/api';

export const useNotifyStore = defineStore('notifyStore', () => {
  const config = ref<FeishuNotifyConfig | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const saveError = ref<string | null>(null);
  const saveSuccess = ref<string | null>(null);
  const testing = ref(false);
  const testResult = ref<FeishuTestResult | null>(null);

  async function loadConfig() {
    loading.value = true;
    try {
      const response = await apiClient.getFeishuConfig();
      config.value = response.data;
    } finally {
      loading.value = false;
    }
  }

  async function saveConfig(payload: FeishuNotifyConfigUpdate) {
    saving.value = true;
    saveError.value = null;
    saveSuccess.value = null;
    try {
      const response = await apiClient.saveFeishuConfig(payload);
      config.value = response.data;
      saveSuccess.value = '飞书通知配置已保存';
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : '保存失败';
      throw error;
    } finally {
      saving.value = false;
    }
  }

  async function sendTest() {
    testing.value = true;
    testResult.value = null;
    try {
      const response = await apiClient.testFeishuNotify();
      testResult.value = response.data;
    } catch (error) {
      testResult.value = {
        success: false,
        message: error instanceof Error ? error.message : '测试失败',
      };
    } finally {
      testing.value = false;
    }
  }

  return {
    config,
    loading,
    saving,
    saveError,
    saveSuccess,
    testing,
    testResult,
    loadConfig,
    saveConfig,
    sendTest,
  };
});
