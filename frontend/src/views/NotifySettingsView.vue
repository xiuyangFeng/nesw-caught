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
  <div class="grid gap-4">
    <header>
      <h1 class="page-title">通知推送设置</h1>
      <p class="page-subtitle">配置飞书应用 Bot 推送通知，支持新闻聚合、自选股异动和 LLM 分析结果推送。</p>
    </header>

    <div class="grid gap-4" data-role="notify-settings-grid">
      <SectionCard title="当前配置" subtitle="飞书通知推送状态">
        <p v-if="!hasConfig" class="text-text-faint">尚未配置飞书通知，完成表单后点击"保存配置"即可生效。</p>
        <template v-else>
          <p class="text-text-faint">
            App ID：{{ notifyStore.config?.app_id ?? '未知' }} ·
            目标：{{ targetTypeLabel }} ({{ notifyStore.config?.target_id ?? '未设置' }})
          </p>
          <p class="text-text-faint">
            通知状态：{{ notifyStore.config?.is_active ? '已启用' : '已关闭' }} ·
            新闻：{{ notifyStore.config?.news_enabled ? '开' : '关' }} ·
            异动：{{ notifyStore.config?.alert_enabled ? '开' : '关' }} ·
            分析：{{ notifyStore.config?.analysis_enabled ? '开' : '关' }}
          </p>
          <p v-if="lastUpdatedLabel" class="text-text-faint">最后更新：{{ lastUpdatedLabel }} HKT</p>
        </template>

        <div v-if="hasConfig" class="mt-3 flex flex-wrap items-center gap-3">
          <button
            class="rounded-full border border-border bg-white/[0.04] px-4 py-2 text-sm font-semibold text-text disabled:cursor-not-allowed disabled:opacity-50"
            data-role="notify-test-button"
            :disabled="notifyStore.testing"
            @click="sendTest"
          >
            {{ notifyStore.testing ? '正在发送…' : '发送测试消息' }}
          </button>
          <p v-if="notifyStore.testResult" :class="notifyStore.testResult.success ? 'text-positive' : 'text-negative'">
            {{ notifyStore.testResult.message }}
          </p>
        </div>
      </SectionCard>

      <SectionCard title="飞书配置" subtitle="修改后即刻覆盖当前设置">
        <form class="grid gap-[14px]" @submit.prevent="submitConfig">
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>App ID *</span>
            <input
              v-model="formState.app_id"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="app_id"
              type="text"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="飞书应用的 App ID"
              required
            />
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>App Secret {{ requiresSecret ? '*' : '' }}</span>
            <input
              v-model="formState.app_secret"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="app_secret"
              type="password"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="留空表示保留当前 Secret"
            />
            <small class="text-text-faint">{{ requiresSecret ? '首次配置必须填写 App Secret' : '不改 Secret 时可留空' }}</small>
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>推送目标类型</span>
            <select
              v-model="formState.target_type"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              :disabled="notifyStore.loading || notifyStore.saving"
            >
              <option value="chat">群聊 (chat_id)</option>
              <option value="user">个人 (open_id)</option>
            </select>
          </label>
          <label class="grid gap-1.5 font-semibold text-text-faint">
            <span>目标 ID *</span>
            <input
              v-model="formState.target_id"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="target_id"
              type="text"
              :disabled="notifyStore.loading || notifyStore.saving"
              :placeholder="formState.target_type === 'chat' ? '飞书群聊的 chat_id' : '飞书用户的 open_id'"
              required
            />
          </label>

          <div class="grid gap-2.5 py-3">
            <label class="flex items-center gap-2.5 font-semibold text-text">
              <input v-model="formState.is_active" type="checkbox" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>启用通知推送</span>
            </label>
            <label class="flex items-center gap-2.5 font-semibold text-text">
              <input v-model="formState.news_enabled" type="checkbox" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>新闻聚合推送</span>
            </label>
            <label class="flex items-center gap-2.5 font-semibold text-text">
              <input v-model="formState.alert_enabled" type="checkbox" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>自选股异动推送</span>
            </label>
            <label class="flex items-center gap-2.5 font-semibold text-text">
              <input v-model="formState.analysis_enabled" type="checkbox" :disabled="notifyStore.loading || notifyStore.saving" />
              <span>LLM 分析结果推送</span>
            </label>
          </div>

          <label v-if="formState.news_enabled" class="grid gap-1.5 font-semibold text-text-faint">
            <span>新闻过滤关键词</span>
            <input
              v-model="formState.news_keywords"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="news_keywords"
              type="text"
              :disabled="notifyStore.loading || notifyStore.saving"
              placeholder="逗号分隔，留空则推全部新闻"
            />
          </label>
          <label v-if="formState.news_enabled" class="grid gap-1.5 font-semibold text-text-faint">
            <span>新闻聚合间隔（分钟）</span>
            <input
              v-model.number="formState.news_batch_interval_minutes"
              data-surface="terminal-field"
              class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
              name="news_batch_interval_minutes"
              type="number"
              :disabled="notifyStore.loading || notifyStore.saving"
              min="5"
              max="1440"
              placeholder="默认 60 分钟"
            />
          </label>

          <div class="flex flex-wrap items-center gap-3">
            <button
              class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              type="submit"
              :disabled="!canSave || notifyStore.saving"
            >
              {{ notifyStore.saving ? '正在保存…' : '保存配置' }}
            </button>
            <p v-if="notifyStore.saveSuccess" class="text-xs text-positive">{{ notifyStore.saveSuccess }}</p>
            <p v-else-if="notifyStore.saveError" class="text-xs text-negative">{{ notifyStore.saveError }}</p>
          </div>
        </form>
      </SectionCard>
    </div>
  </div>
</template>
