<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { useLlmStore } from '../stores/llmStore';
import { formatMarketTime } from '../utils/time';

const llmStore = useLlmStore();

const formState = reactive({
  provider_name: '',
  display_name: '',
  base_url: '',
  model_name: '',
  api_key: '',
});

const hasConfig = computed(() => llmStore.config?.configured === true);
const requiresKey = computed(() => !hasConfig.value);
const canSave = computed(() => {
  const providerValid = formState.provider_name.trim().length > 0;
  const modelValid = formState.model_name.trim().length > 0;
  const keyValid = formState.api_key.trim().length > 0;
  return providerValid && modelValid && (!requiresKey.value || keyValid);
});

const lastUpdatedLabel = computed(() => {
  if (!llmStore.config?.updated_at) {
    return null;
  }
  return formatMarketTime(llmStore.config.updated_at, 'hk');
});

watch(
  () => llmStore.config,
  (config) => {
    formState.provider_name = config?.provider_name ?? '';
    formState.display_name = config?.display_name ?? '';
    formState.base_url = config?.base_url ?? '';
    formState.model_name = config?.model_name ?? '';
    if (!config?.configured) {
      formState.api_key = '';
    }
  },
  { immediate: true },
);

async function submitConfig() {
  if (!canSave.value) {
    return;
  }

  const trimmedKey = formState.api_key.trim();
  const payload = {
    provider_name: formState.provider_name.trim(),
    display_name: formState.display_name.trim() || null,
    base_url: formState.base_url.trim() || null,
    model_name: formState.model_name.trim(),
    api_key: trimmedKey ? trimmedKey : undefined,
  };

  try {
    await llmStore.saveConfig(payload);
    formState.api_key = '';
  } catch {
    // error message surfaced by store
  }
}

async function submitConnectionTest() {
  if (!hasConfig.value) {
    return;
  }
  try {
    await llmStore.testConnection();
  } catch {
    // error message surfaced by store
  }
}

onMounted(() => {
  if (!llmStore.config) {
    llmStore.loadConfig();
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">LLM Settings</h1>
        <p class="page-subtitle">配置用于新闻详情页的 LLM provider、模型与 API key。</p>
      </div>
    </header>

    <div class="settings-grid">
      <SectionCard title="当前配置" subtitle="当前生效的单套 provider">
        <p class="status-text negative" v-if="llmStore.loadError">{{ llmStore.loadError }}</p>
        <p class="subtle" v-if="!hasConfig">尚未配置任何 LLM，完成表单后点击“保存配置”即可生效。</p>
        <p class="subtle" v-else>
          当前模型：{{ llmStore.config?.provider_name ?? '未知' }} /
          {{ llmStore.config?.model_name ?? '未知' }} · {{ llmStore.config?.display_name ?? '未填写显示名' }}
        </p>
        <p class="subtle" v-if="lastUpdatedLabel">最后更新：{{ lastUpdatedLabel }} HKT</p>
      </SectionCard>

      <SectionCard title="活动配置" subtitle="修改后即刻覆盖当前设置">
        <form class="config-form" @submit.prevent="submitConfig">
          <label class="field">
            <span>Provider 名称 *</span>
            <input
              name="provider_name"
              type="text"
              v-model="formState.provider_name"
              data-surface="terminal-field"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="例如 openai_compatible"
              required
            />
          </label>
          <label class="field">
            <span>显示名称</span>
            <input
              name="display_name"
              type="text"
              v-model="formState.display_name"
              data-surface="terminal-field"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="仅用于界面展示，可自定义"
            />
          </label>
          <label class="field">
            <span>Base URL</span>
            <input
              name="base_url"
              type="text"
              v-model="formState.base_url"
              data-surface="terminal-field"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="可留空但建议填写 API 地址"
            />
          </label>
          <label class="field">
            <span>Model 名称 *</span>
            <input
              name="model_name"
              type="text"
              v-model="formState.model_name"
              data-surface="terminal-field"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="例如 deepseek-chat"
              required
            />
          </label>
          <label class="field">
            <span>API Key {{ requiresKey ? '*' : '' }}</span>
            <input
              name="api_key"
              type="password"
              v-model="formState.api_key"
              data-surface="terminal-field"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="留空表示保留当前 key"
            />
            <small class="subtle">{{ requiresKey ? '首次配置必须填写 API key' : '不改 key 时可留空' }}</small>
          </label>

          <div class="form-footer">
            <button class="save-button" type="submit" :disabled="!canSave || llmStore.saving">
              {{ llmStore.saving ? '正在保存…' : '保存配置' }}
            </button>
            <button
              v-if="hasConfig"
              class="test-button"
              type="button"
              data-testid="test-connection-button"
              :disabled="llmStore.loading || llmStore.saving || llmStore.testingConnection"
              @click="submitConnectionTest"
            >
              {{ llmStore.testingConnection ? '测试中…' : '测试连接' }}
            </button>
            <p v-if="llmStore.saveSuccess" class="status-text positive">{{ llmStore.saveSuccess }}</p>
            <p v-else-if="llmStore.saveError" class="status-text negative">{{ llmStore.saveError }}</p>
            <p v-if="llmStore.testSuccess" class="status-text positive">{{ llmStore.testSuccess }}</p>
            <p v-else-if="llmStore.testError" class="status-text negative">{{ llmStore.testError }}</p>
          </div>
          <p class="subtle">测试连接只会验证当前已保存并生效的配置，不会读取未保存的表单修改。</p>
        </form>
      </SectionCard>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.settings-grid {
  display: grid;
  gap: 16px;
}

.config-form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
  font-weight: 600;
  color: var(--text-faint);
}

.field input {
  border-radius: 12px;
  border: 1px solid var(--border);
  padding: 10px 14px;
  font: inherit;
  background: var(--field-bg);
  color: var(--text);
  transition: border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}

.field input::placeholder {
  color: var(--text-faint);
}

.field input:hover {
  border-color: rgba(125, 211, 252, 0.18);
}

.field input:focus {
  border-color: rgba(125, 211, 252, 0.4);
  box-shadow: 0 0 0 3px rgba(125, 211, 252, 0.12);
}

.field small.subtle {
  color: var(--text-faint);
}

.form-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.save-button,
.test-button {
  border: none;
  border-radius: 999px;
  padding: 10px 20px;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.save-button {
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
}

.test-button {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
}

.save-button:hover:not(:disabled),
.test-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.save-button:hover:not(:disabled) {
  box-shadow: 0 10px 24px rgba(58, 169, 245, 0.24);
}

.test-button:hover:not(:disabled) {
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.24);
}

.save-button:disabled,
.test-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-text {
  font-size: 12px;
}

.status-text.positive {
  color: var(--positive);
}

.status-text.negative {
  color: var(--negative);
}
</style>
