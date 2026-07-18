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
  // 告警治理（去重 / 免打扰 / 分级 / 合并）——留空 / 置 0 即关闭，默认保守。
  governance: {
    quiet_hours_start: '',
    quiet_hours_end: '',
    quiet_hours_tz: 'Asia/Shanghai',
    dedupe_window_minutes: 0,
    digest_window_minutes: 0,
    digest_threshold: 3,
    critical_change_percent: 8,
  },
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
    const gov = config?.governance;
    formState.governance.quiet_hours_start = gov?.quiet_hours_start ?? '';
    formState.governance.quiet_hours_end = gov?.quiet_hours_end ?? '';
    formState.governance.quiet_hours_tz = gov?.quiet_hours_tz ?? 'Asia/Shanghai';
    formState.governance.dedupe_window_minutes = gov?.dedupe_window_minutes ?? 0;
    formState.governance.digest_window_minutes = gov?.digest_window_minutes ?? 0;
    formState.governance.digest_threshold = gov?.digest_threshold ?? 3;
    formState.governance.critical_change_percent = gov?.critical_change_percent ?? 8;
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
    governance: {
      quiet_hours_start: formState.governance.quiet_hours_start.trim() || null,
      quiet_hours_end: formState.governance.quiet_hours_end.trim() || null,
      quiet_hours_tz: formState.governance.quiet_hours_tz.trim() || 'Asia/Shanghai',
      dedupe_window_minutes: Number(formState.governance.dedupe_window_minutes) || 0,
      digest_window_minutes: Number(formState.governance.digest_window_minutes) || 0,
      digest_threshold: Number(formState.governance.digest_threshold) || 3,
      critical_change_percent: Number(formState.governance.critical_change_percent) || 8,
    },
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
          <p v-if="notifyStore.testResult" :class="notifyStore.testResult.success ? 'text-success' : 'text-danger'">
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

          <div class="mt-1 rounded-xl border border-border bg-white/[0.02] p-4">
            <div class="mb-1 flex items-center gap-2">
              <span class="text-sm font-semibold text-system">告警治理</span>
              <span class="rounded-full border border-system/40 bg-system/10 px-2 py-0.5 text-[10px] font-semibold text-system">
                去重 · 免打扰 · 分级 · 合并
              </span>
            </div>
            <p class="mb-3 text-xs text-text-faint">
              让通知从"吵"变"可信"：留空 / 置 0 表示关闭该项（默认保守，与旧版行为一致）。配置即刻生效，保存后随通知配置一并落地。
            </p>

            <div class="grid gap-[14px]">
              <div class="grid gap-1.5">
                <span class="text-xs font-semibold text-text-faint">免打扰时段</span>
                <div class="flex flex-wrap items-center gap-2">
                  <input
                    v-model="formState.governance.quiet_hours_start"
                    data-surface="terminal-field"
                    class="rounded-xl border border-border bg-field px-3 py-2 text-text"
                    type="time"
                    :disabled="notifyStore.loading || notifyStore.saving"
                  />
                  <span class="text-text-faint">至</span>
                  <input
                    v-model="formState.governance.quiet_hours_end"
                    data-surface="terminal-field"
                    class="rounded-xl border border-border bg-field px-3 py-2 text-text"
                    type="time"
                    :disabled="notifyStore.loading || notifyStore.saving"
                  />
                  <input
                    v-model="formState.governance.quiet_hours_tz"
                    data-surface="terminal-field"
                    class="min-w-[160px] flex-1 rounded-xl border border-border bg-field px-3 py-2 text-text"
                    type="text"
                    placeholder="时区，如 Asia/Shanghai"
                    :disabled="notifyStore.loading || notifyStore.saving"
                  />
                </div>
                <small class="text-text-faint">时段内低优先级异动暂缓到结束后再发；极端异动（critical）不受限制照常推送。两端留空即关闭。</small>
              </div>

              <label class="grid gap-1.5">
                <span class="text-xs font-semibold text-text-faint">分级阈值：涨跌幅（%）达到即判为极端异动</span>
                <input
                  v-model.number="formState.governance.critical_change_percent"
                  data-surface="terminal-field"
                  class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
                  type="number"
                  min="0"
                  step="0.5"
                  :disabled="notifyStore.loading || notifyStore.saving"
                  placeholder="默认 8.0"
                />
                <small class="text-text-faint">达到该绝对涨跌幅的异动升级为 critical，绕过免打扰与合并，第一时间送达。</small>
              </label>

              <label class="grid gap-1.5">
                <span class="text-xs font-semibold text-text-faint">去重窗口（分钟）</span>
                <input
                  v-model.number="formState.governance.dedupe_window_minutes"
                  data-surface="terminal-field"
                  class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
                  type="number"
                  min="0"
                  max="1440"
                  :disabled="notifyStore.loading || notifyStore.saving"
                  placeholder="0 = 关闭"
                />
                <small class="text-text-faint">同一标的同类异动在窗口内只发一次，抑制反复越界刷屏。0 表示关闭。</small>
              </label>

              <div class="grid gap-[14px] sm:grid-cols-2">
                <label class="grid gap-1.5">
                  <span class="text-xs font-semibold text-text-faint">合并窗口（分钟）</span>
                  <input
                    v-model.number="formState.governance.digest_window_minutes"
                    data-surface="terminal-field"
                    class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
                    type="number"
                    min="0"
                    max="1440"
                    :disabled="notifyStore.loading || notifyStore.saving"
                    placeholder="0 = 关闭"
                  />
                  <small class="text-text-faint">窗口内累积的多条异动合并成一张摘要卡片。0 表示逐条发送。</small>
                </label>
                <label class="grid gap-1.5">
                  <span class="text-xs font-semibold text-text-faint">合并阈值（条）</span>
                  <input
                    v-model.number="formState.governance.digest_threshold"
                    data-surface="terminal-field"
                    class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text"
                    type="number"
                    min="2"
                    max="50"
                    :disabled="notifyStore.loading || notifyStore.saving"
                    placeholder="默认 3"
                  />
                  <small class="text-text-faint">窗口结束时累计达到该条数才合并，不足则仍逐条发送。</small>
                </label>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <button
              class="rounded-full bg-accent px-5 py-2.5 font-semibold text-bg disabled:cursor-not-allowed disabled:opacity-50"
              type="submit"
              :disabled="!canSave || notifyStore.saving"
            >
              {{ notifyStore.saving ? '正在保存…' : '保存配置' }}
            </button>
            <p v-if="notifyStore.saveSuccess" class="text-xs text-success">{{ notifyStore.saveSuccess }}</p>
            <p v-else-if="notifyStore.saveError" class="text-xs text-danger">{{ notifyStore.saveError }}</p>
          </div>
        </form>
      </SectionCard>
    </div>
  </div>
</template>
