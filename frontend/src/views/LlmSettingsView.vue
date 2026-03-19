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
  <div class="grid gap-4">
    <header>
      <h1 class="page-title">LLM Settings</h1>
      <p class="page-subtitle">配置用于新闻详情页的 LLM provider、模型与 API key。</p>
    </header>

    <div class="grid gap-4" data-role="llm-settings-grid">
      <SectionCard title="当前配置" subtitle="当前生效的单套 provider">
        <p v-if="llmStore.loadError" class="text-negative">{{ llmStore.loadError }}</p>
        <p v-if="!hasConfig" class="text-text-faint">尚未配置任何 LLM，完成表单后点击“保存配置”即可生效。</p>
        <p v-else class="text-text-faint">
          当前模型：{{ llmStore.config?.provider_name ?? '未知' }} /
          {{ llmStore.config?.model_name ?? '未知' }} · {{ llmStore.config?.display_name ?? '未填写显示名' }}
        </p>
        <p v-if="lastUpdatedLabel" class="text-text-faint">最后更新：{{ lastUpdatedLabel }} HKT</p>
      </SectionCard>

      <SectionCard title="活动配置" subtitle="修改后即刻覆盖当前设置">
        <form class="grid gap-[14px]" @submit.prevent="submitConfig">
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>Provider 名称 *</span>
            <input
              v-model="formState.provider_name"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="provider_name"
              type="text"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="例如 openai_compatible"
              required
            />
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>显示名称</span>
            <input
              v-model="formState.display_name"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="display_name"
              type="text"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="仅用于界面展示，可自定义"
            />
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>Base URL</span>
            <input
              v-model="formState.base_url"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="base_url"
              type="text"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="可留空但建议填写 API 地址"
            />
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>Model 名称 *</span>
            <input
              v-model="formState.model_name"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="model_name"
              type="text"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="例如 deepseek-chat"
              required
            />
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>API Key {{ requiresKey ? '*' : '' }}</span>
            <input
              v-model="formState.api_key"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="api_key"
              type="password"
              :disabled="llmStore.loading || llmStore.saving"
              placeholder="留空表示保留当前 key"
            />
            <small class="text-text-faint">{{ requiresKey ? '首次配置必须填写 API key' : '不改 key 时可留空' }}</small>
          </label>

          <div class="flex flex-wrap items-center gap-3">
            <button
              class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              type="submit"
              :disabled="!canSave || llmStore.saving"
            >
              {{ llmStore.saving ? '正在保存…' : '保存配置' }}
            </button>
            <button
              v-if="hasConfig"
              class="rounded-full bg-[linear-gradient(135deg,#0f766e,#14b8a6)] px-5 py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              type="button"
              data-testid="test-connection-button"
              :disabled="llmStore.loading || llmStore.saving || llmStore.testingConnection"
              @click="submitConnectionTest"
            >
              {{ llmStore.testingConnection ? '测试中…' : '测试连接' }}
            </button>
            <p v-if="llmStore.saveSuccess" class="text-xs text-positive">{{ llmStore.saveSuccess }}</p>
            <p v-else-if="llmStore.saveError" class="text-xs text-negative">{{ llmStore.saveError }}</p>
            <p v-if="llmStore.testSuccess" class="text-xs text-positive">{{ llmStore.testSuccess }}</p>
            <p v-else-if="llmStore.testError" class="text-xs text-negative">{{ llmStore.testError }}</p>
          </div>
          <p class="text-text-faint">测试连接只会验证当前已保存并生效的配置，不会读取未保存的表单修改。</p>
        </form>
      </SectionCard>
    </div>
  </div>
</template>
