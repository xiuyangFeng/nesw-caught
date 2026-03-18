<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { useNotifyStore } from '../stores/notifyStore';
import { formatMarketTime } from '../utils/time';

const notifyStore = useNotifyStore();

const formState = reactive({
  app_id: '',
  app_secret: '',
  target_type: 'chat',
  target_id: '',
  news_enabled: true,
  news_keywords: '',
  news_batch_interval_minutes: 60,
  alert_enabled: true,
  analysis_enabled: true,
  is_active: true,
});

const hasConfig = computed(() => notifyStore.config?.configured === true);
const requiresSecret = computed(() => !hasConfig.value);
const canSave = computed(() => {
  const appIdValid = formState.app_id.trim().length > 0;
  const targetIdValid = formState.target_id.trim().length > 0;
  const secretValid = formState.app_secret.trim().length > 0;
  return appIdValid && targetIdValid && (!requiresSecret.value || secretValid);
});

const lastUpdatedLabel = computed(() => {
  if (!notifyStore.config?.updated_at) return null;
  return formatMarketTime(notifyStore.config.updated_at, 'hk');
});

const targetTypeLabel = computed(() => {
  if (notifyStore.config?.target_type === 'chat') return '群聊';
  if (notifyStore.config?.target_type === 'user') return '个人';
  return '未设置';
});

watch(
  () => notifyStore.config,
  (config) => {
    formState.app_id = config?.app_id ?? '';
    formState.target_type = config?.target_type ?? 'chat';
    formState.target_id = config?.target_id ?? '';
    formState.news_enabled = config?.news_enabled ?? true;
    formState.news_keywords = config?.news_keywords ?? '';
    formState.news_batch_interval_minutes = config?.news_batch_interval_minutes ?? 60;
    formState.alert_enabled = config?.alert_enabled ?? true;
    formState.analysis_enabled = config?.analysis_enabled ?? true;
    formState.is_active = config?.is_active ?? true;
    if (!config?.configured) {
      formState.app_secret = '';
    }
  },
  { immediate: true },
);

async function submitConfig() {
  if (!canSave.value) return;

  const trimmedSecret = formState.app_secret.trim();
  const payload = {
    app_id: formState.app_id.trim(),
    app_secret: trimmedSecret || undefined,
    target_type: formState.target_type,
    target_id: formState.target_id.trim(),
    news_enabled: formState.news_enabled,
    news_keywords: formState.news_keywords.trim() || null,
    news_batch_interval_minutes: formState.news_batch_interval_minutes,
    alert_enabled: formState.alert_enabled,
    analysis_enabled: formState.analysis_enabled,
    is_active: formState.is_active,
  };

  try {
    await notifyStore.saveConfig(payload);
    formState.app_secret = '';
  } catch {
    // error surfaced by store
  }
}

async function sendTest() {
  await notifyStore.sendTest();
}

onMounted(() => {
  if (!notifyStore.config) {
    notifyStore.loadConfig();
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">通知推送设置</h1>
        <p class="page-subtitle">配置飞书应用 Bot 推送通知，支持新闻聚合、自选股异动和 LLM 分析结果推送。</p>
      </div>
    </header>

    <div class="settings-grid">
      <SectionCard title="当前配置" subtitle="飞书通知推送状态">
        <p class="subtle" v-if="!hasConfig">尚未配置飞书通知，完成表单后点击"保存配置"即可生效。</p>
        <template v-else>
          <p class="subtle">
            App ID：{{ notifyStore.config?.app_id ?? '未知' }} ·
            目标：{{ targetTypeLabel }} ({{ notifyStore.config?.target_id ?? '未设置' }})
          </p>
          <p class="subtle">
            通知状态：{{ notifyStore.config?.is_active ? '已启用' : '已关闭' }} ·
            新闻：{{ notifyStore.config?.news_enabled ? '开' : '关' }} ·
            异动：{{ notifyStore.config?.alert_enabled ? '开' : '关' }} ·
            分析：{{ notifyStore.config?.analysis_enabled ? '开' : '关' }}
          </p>
          <p class="subtle" v-if="lastUpdatedLabel">最后更新：{{ lastUpdatedLabel }} HKT</p>
        </template>

        <div class="test-section" v-if="hasConfig">
          <button
            class="test-button"
            :disabled="notifyStore.testing"
            @click="sendTest"
          >
            {{ notifyStore.testing ? '正在发送…' : '发送测试消息' }}
          </button>
          <p v-if="notifyStore.testResult" :class="['status-text', notifyStore.testResult.success ? 'positive' : 'negative']">
            {{ notifyStore.testResult.message }}
          </p>
        </div>
      </SectionCard>

      <SectionCard title="飞书配置" subtitle="修改后即刻覆盖当前设置">
        <form class="config-form" @submit.prevent="submitConfig">
          <label class="field">
            <span>App ID *</span>
            <input
              name="app_id"
              type="text"
              v-model="formState.app_id"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="飞书应用的 App ID"
              required
            />
          </label>
          <label class="field">
            <span>App Secret {{ requiresSecret ? '*' : '' }}</span>
            <input
              name="app_secret"
              type="password"
              v-model="formState.app_secret"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="留空表示保留当前 Secret"
            />
            <small class="subtle">{{ requiresSecret ? '首次配置必须填写 App Secret' : '不改 Secret 时可留空' }}</small>
          </label>

          <label class="field">
            <span>推送目标类型</span>
            <select
              v-model="formState.target_type"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
            >
              <option value="chat">群聊 (chat_id)</option>
              <option value="user">个人 (open_id)</option>
            </select>
          </label>
          <label class="field">
            <span>目标 ID *</span>
            <input
              name="target_id"
              type="text"
              v-model="formState.target_id"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
              :placeholder="formState.target_type === 'chat' ? '飞书群聊的 chat_id' : '飞书用户的 open_id'"
              required
            />
          </label>

          <div class="toggle-group">
            <label class="toggle-field">
              <input type="checkbox" v-model="formState.is_active" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>启用通知推送</span>
            </label>
            <label class="toggle-field">
              <input type="checkbox" v-model="formState.news_enabled" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>新闻聚合推送</span>
            </label>
            <label class="toggle-field">
              <input type="checkbox" v-model="formState.alert_enabled" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>自选股异动推送</span>
            </label>
            <label class="toggle-field">
              <input type="checkbox" v-model="formState.analysis_enabled" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>LLM 分析结果推送</span>
            </label>
          </div>

          <label class="field" v-if="formState.news_enabled">
            <span>新闻过滤关键词</span>
            <input
              name="news_keywords"
              type="text"
              v-model="formState.news_keywords"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="逗号分隔，留空则推全部新闻"
            />
          </label>
          <label class="field" v-if="formState.news_enabled">
            <span>新闻聚合间隔（分钟）</span>
            <input
              name="news_batch_interval_minutes"
              type="number"
              v-model.number="formState.news_batch_interval_minutes"
              data-surface="terminal-field"
              :disabled="notifyStore.loading || notifyStore.saving"
              min="5"
              max="1440"
              placeholder="默认 60 分钟"
            />
          </label>

          <div class="form-footer">
            <button class="save-button" type="submit" :disabled="!canSave || notifyStore.saving">
              {{ notifyStore.saving ? '正在保存…' : '保存配置' }}
            </button>
            <p v-if="notifyStore.saveSuccess" class="status-text positive">{{ notifyStore.saveSuccess }}</p>
            <p v-else-if="notifyStore.saveError" class="status-text negative">{{ notifyStore.saveError }}</p>
          </div>
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

.field input,
.field select {
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

.field input:hover,
.field select:hover {
  border-color: rgba(125, 211, 252, 0.18);
}

.field input:focus,
.field select:focus {
  border-color: rgba(125, 211, 252, 0.4);
  box-shadow: 0 0 0 3px rgba(125, 211, 252, 0.12);
}

.field small.subtle {
  color: var(--text-faint);
}

.toggle-group {
  display: grid;
  gap: 10px;
  padding: 12px 0;
}

.toggle-field {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
}

.toggle-field input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--accent, #3aa9f5);
  cursor: pointer;
}

.test-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.test-button {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 16px;
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease;
}

.test-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(125, 211, 252, 0.3);
  transform: translateY(-1px);
}

.test-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.save-button {
  border: none;
  border-radius: 999px;
  padding: 10px 20px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.save-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(58, 169, 245, 0.24);
}

.save-button:disabled {
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
