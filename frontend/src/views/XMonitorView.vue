<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import { useXMonitorStore } from '../stores/xMonitorStore';
import type { XPost } from '../types/api';
import { sentimentText } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

const xMonitorStore = useXMonitorStore();
const createForm = reactive({
  handle: '',
  display_name: '',
  market_focus: 'us',
  tier: 'watch',
  priority: '0',
  notes: '',
});

const accountOptions = computed(() => xMonitorStore.accounts.filter((item) => item.is_active));
const evidenceFeed = computed(() => xMonitorStore.radar?.evidence_stream ?? xMonitorStore.posts);
const visiblePosts = computed(() =>
  evidenceFeed.value.filter((post) => {
    const account = xMonitorStore.getAccountByHandle(post.account_handle);
    const tier = account?.tier ?? 'watch';
    if (xMonitorStore.searchTierFilter && tier !== xMonitorStore.searchTierFilter) {
      return false;
    }
    if (!xMonitorStore.searchTierFilter && tier === 'muted') {
      return false;
    }
    return true;
  }),
);
const prioritySignals = computed(() => xMonitorStore.radar?.priority_signals ?? []);
const macroClusters = computed(() => xMonitorStore.radar?.macro_clusters ?? []);
const bannerTone = computed(() => {
  if (xMonitorStore.health?.enabled === false) return 'warning';
  if (xMonitorStore.health && !xMonitorStore.health.healthy) return 'danger';
  return xMonitorStore.usingMock ? 'warning' : 'default';
});
const bannerTitle = computed(() => {
  if (xMonitorStore.health?.enabled === false) return 'X Radar 未启用';
  if (xMonitorStore.health && !xMonitorStore.health.configured) return 'twitterapi.io API key 未配置';
  if (xMonitorStore.health && !xMonitorStore.health.healthy) return 'twitterapi.io 当前不可用';
  return xMonitorStore.usingMock ? '已启用 mock 兼容层' : 'X Radar 已连接到 twitterapi.io';
});
const bannerDetail = computed(() => {
  if (!xMonitorStore.health) return '健康状态加载中。';
  return `数据源状态：${xMonitorStore.health.status}；最近成功：${
    xMonitorStore.health.last_success_at ? formatMarketTime(xMonitorStore.health.last_success_at, 'us') : '--'
  } ${getMarketTimezoneLabel('us')}`;
});
const nextRefreshText = computed(() => {
  const nextRefreshAt = xMonitorStore.lastRefresh?.next_refresh_at;
  if (!nextRefreshAt) return null;
  return `${formatMarketTime(nextRefreshAt, 'us')} ${getMarketTimezoneLabel('us')}`;
});
const policySummary = computed(() => {
  if (!xMonitorStore.health) return null;
  return `请求节流 ${xMonitorStore.health.min_interval_seconds} 秒/次 · 账号刷新冷却 ${xMonitorStore.health.refresh_cooldown_hours} 小时`;
});
const signalSummaryTitle = computed(() => `当前识别 ${prioritySignals.value.length} 条优先异动，证据流包含 ${visiblePosts.value.length} 条帖子`);
const feedSummaryDetail = computed(() => {
  const detailParts: string[] = [];
  if (policySummary.value) detailParts.push(policySummary.value);
  const refreshAt = xMonitorStore.lastRefresh?.finished_at ?? xMonitorStore.health?.last_success_at ?? null;
  if (refreshAt) detailParts.push(`最近刷新 ${formatMarketTime(refreshAt, 'us')} ${getMarketTimezoneLabel('us')}`);
  return detailParts.join(' · ');
});

function translationState(post: XPost) {
  const key = xMonitorStore.getTranslationKey(post);
  return (
    xMonitorStore.translationsByKey[key] ?? {
      status: 'idle',
      translated_text: null,
      error: null,
    }
  );
}

function tierTone(tier: string) {
  if (tier === 'core') return 'positive';
  if (tier === 'muted') return 'negative';
  return 'neutral';
}

async function submitCreateAccount() {
  const created = await xMonitorStore.createAccount({
    handle: createForm.handle.trim().replace(/^@+/, ''),
    display_name: createForm.display_name.trim(),
    market_focus: createForm.market_focus || null,
    is_active: true,
    priority: Number(createForm.priority || '0'),
    tier: createForm.tier as 'core' | 'watch' | 'muted',
    notes: createForm.notes.trim() || null,
  });
  if (!created) {
    return;
  }
  createForm.handle = '';
  createForm.display_name = '';
  createForm.market_focus = 'us';
  createForm.tier = 'watch';
  createForm.priority = '0';
  createForm.notes = '';
}

async function toggleAccount(account: { handle: string; is_active: boolean }) {
  await xMonitorStore.updateAccount(account.handle, { is_active: !account.is_active });
}

async function removeAccount(handle: string) {
  await xMonitorStore.deleteAccount(handle);
}

watch(
  () => ({ ...xMonitorStore.filters }),
  async () => {
    await xMonitorStore.loadPosts();
  },
  { deep: true },
);

onMounted(async () => {
  await xMonitorStore.bootstrap();
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">X Radar</h1>
        <p class="page-subtitle">以自定义账号池为主、宏观政策事件为辅，优先输出值得看的早期异动信号。</p>
      </div>
      <StaleBadge :stale="xMonitorStore.stale" label="X Radar" />
    </header>

    <StatusBanner :title="bannerTitle" :tone="bannerTone" :detail="bannerDetail">
      <button
        class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-[14px] py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
        type="button"
        :disabled="xMonitorStore.refreshLoading"
        @click="xMonitorStore.refreshPosts()"
      >
        {{ xMonitorStore.refreshLoading ? '刷新中...' : '手动刷新' }}
      </button>
    </StatusBanner>
    <p v-if="xMonitorStore.refreshError" class="-mt-1 text-sm text-danger" data-role="x-refresh-error">{{ xMonitorStore.refreshError }}</p>
    <p v-if="policySummary" class="-mt-1 text-sm text-text-faint">{{ policySummary }}</p>
    <p v-if="xMonitorStore.lastRefresh?.skipped && nextRefreshText" class="-mt-1 text-sm text-text-faint">
      冷却中，下次可刷新：{{ nextRefreshText }}
    </p>

    <section class="grid gap-4 xl:grid-cols-[1.2fr_0.88fr]" data-role="x-monitor-layout">
      <div class="grid gap-4">
        <SectionCard title="Priority Radar" subtitle="按优先级排序的早期异动信号，而不是原始帖子时间流">
          <LoadingBlock :loading="xMonitorStore.radarLoading || xMonitorStore.healthLoading" :empty="prioritySignals.length === 0" empty-text="当前还没有优先异动信号">
            <div class="mb-3 grid gap-1.5 rounded-[14px] border-l-[3px] border-l-system bg-[linear-gradient(135deg,rgba(15,27,40,0.96),rgba(10,19,31,0.86))] px-4 py-3" data-role="feed-summary">
              <p class="m-0 text-[0.68rem] uppercase tracking-[0.14em] text-system">Radar Status</p>
              <p class="m-0 text-[1.05rem] leading-[1.45]" data-role="feed-summary-title">{{ signalSummaryTitle }}</p>
              <p class="m-0 text-[0.8rem] leading-[1.45] text-text-faint" data-role="feed-summary-detail">{{ feedSummaryDetail }}</p>
            </div>
            <div class="grid gap-3">
              <article
                v-for="signal in prioritySignals"
                :key="signal.id"
                class="grid gap-3 rounded-[18px] border border-border bg-panel-stronger p-4"
                data-role="priority-signal-card"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="grid gap-1">
                    <strong>{{ signal.title }}</strong>
                    <span class="text-sm text-text-faint">
                      {{ signal.market.toUpperCase() }}
                      <template v-if="signal.macro_tag"> · {{ signal.macro_tag }}</template>
                      <template v-if="signal.primary_symbol"> · {{ signal.primary_symbol }}</template>
                    </span>
                  </div>
                  <span class="pill neutral">P{{ Math.round(signal.priority_score) }}</span>
                </div>
                <p class="m-0 text-sm leading-6 text-text-soft">{{ signal.summary }}</p>
                <div class="flex flex-wrap gap-2 text-xs text-text-faint">
                  <span>信号类型 {{ signal.signal_type }}</span>
                  <span>来源 {{ signal.source_count }} 个</span>
                  <span>置信度 {{ signal.confidence_score.toFixed(2) }}</span>
                  <span>最近时间 {{ formatMarketTime(signal.last_seen_at, signal.market) }} {{ getMarketTimezoneLabel(signal.market) }}</span>
                </div>
              </article>
            </div>
          </LoadingBlock>
        </SectionCard>

        <SectionCard title="Macro Watch" subtitle="用主题簇快速看清宏观 / 政策方向是否开始形成讨论">
          <LoadingBlock :loading="xMonitorStore.radarLoading || xMonitorStore.healthLoading" :empty="macroClusters.length === 0" empty-text="当前没有宏观事件簇">
            <div class="grid gap-3 md:grid-cols-2">
              <article
                v-for="cluster in macroClusters"
                :key="cluster.macro_tag"
                class="grid gap-2 rounded-[18px] border border-border bg-panel-stronger p-4"
                data-role="macro-cluster-card"
              >
                <strong>{{ cluster.title }}</strong>
                <div class="flex flex-wrap gap-2 text-sm text-text-faint">
                  <span>tag {{ cluster.macro_tag }}</span>
                  <span>{{ cluster.signal_count }} 条信号</span>
                  <span>{{ cluster.source_count }} 个来源</span>
                </div>
              </article>
            </div>
          </LoadingBlock>
        </SectionCard>

        <SectionCard title="Evidence Feed" subtitle="原始帖子作为证据层保留，便于快速核查上下文">
          <LoadingBlock :loading="xMonitorStore.loading || xMonitorStore.healthLoading" :empty="visiblePosts.length === 0" empty-text="当前没有可展示的 X 帖子">
            <div
              class="grid rounded-2xl border border-system/10 bg-[rgba(10,18,29,0.58)] shell:max-h-[clamp(420px,56vh,720px)] shell:overflow-y-auto"
              data-role="post-feed"
            >
              <article
                v-for="post in visiblePosts"
                :key="post.id"
                class="grid gap-2 border-b border-system/10 px-[14px] py-3 last:border-b-0"
                data-role="post-list-item"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    <strong>{{ post.account_display_name }}</strong>
                    <span class="text-text-faint">@{{ post.account_handle }}</span>
                    <span class="text-text-faint">{{ formatMarketTime(post.posted_at ?? post.captured_at, post.market) }} {{ getMarketTimezoneLabel(post.market) }}</span>
                    <span class="text-text-faint">{{ post.market.toUpperCase() }}</span>
                  </div>
                  <span class="pill" :class="post.sentiment_label">{{ sentimentText(post.sentiment_label) }}</span>
                </div>
                <p class="m-0 text-[0.92rem] leading-[1.45] text-text-soft">{{ post.content_text }}</p>
                <div class="flex flex-wrap items-center gap-2.5">
                  <button
                    class="rounded-full border border-system/25 bg-[rgba(16,31,45,0.92)] px-3 py-1.5 text-[0.82rem] font-semibold text-[#d7f1ff] disabled:cursor-not-allowed disabled:opacity-60"
                    data-role="translate-button"
                    type="button"
                    :disabled="translationState(post).status === 'loading'"
                    @click="xMonitorStore.translatePost(post)"
                  >
                    {{ translationState(post).status === 'loading' ? '翻译中...' : '翻译' }}
                  </button>
                  <p v-if="translationState(post).status === 'error' && translationState(post).error" class="m-0 text-[0.84rem] text-[#fca5a5]">
                    {{ translationState(post).error }}
                  </p>
                </div>
                <p v-if="translationState(post).status === 'success' && translationState(post).translated_text" class="m-0 text-[0.84rem] text-[#d9edf8]">
                  {{ translationState(post).translated_text }}
                </p>
                <div class="mt-0 flex flex-wrap gap-2 text-[0.82rem] text-muted">
                  <span>相关度 {{ post.relevance_score?.toFixed(2) ?? '--' }}</span>
                  <span v-if="post.symbols.length > 0">{{ post.symbols.join(' · ') }}</span>
                  <span v-else>暂无股票命中</span>
                  <a v-if="post.canonical_url" :href="post.canonical_url" target="_blank" rel="noreferrer">打开原帖</a>
                </div>
              </article>
            </div>
          </LoadingBlock>
        </SectionCard>
      </div>

      <SectionCard title="状态与账号管理" subtitle="provider 状态、监控名单维护和帖子过滤条件">
        <div class="grid grid-cols-3 gap-2.5">
          <div class="grid gap-1 rounded-2xl border border-border bg-panel-stronger p-3.5">
            <span class="text-text-faint">模块</span>
            <strong>{{ xMonitorStore.health?.enabled ? '已启用' : '未启用' }}</strong>
          </div>
          <div class="grid gap-1 rounded-2xl border border-border bg-panel-stronger p-3.5">
            <span class="text-text-faint">Provider</span>
            <strong>{{ xMonitorStore.health?.healthy ? '健康' : '异常' }}</strong>
          </div>
          <div class="grid gap-1 rounded-2xl border border-border bg-panel-stronger p-3.5">
            <span class="text-text-faint">最近刷新</span>
            <strong>
              {{
                xMonitorStore.lastRefresh?.finished_at
                  ? formatMarketTime(xMonitorStore.lastRefresh.finished_at, 'us')
                  : xMonitorStore.health?.last_success_at
                    ? formatMarketTime(xMonitorStore.health.last_success_at, 'us')
                    : '--'
              }}
            </strong>
          </div>
        </div>

        <div class="mt-4 flex gap-2">
          <select v-model="xMonitorStore.filters.account_handle" class="flex-1 rounded-xl border border-border bg-field px-3 py-2.5 text-text">
            <option value="">全部博主</option>
            <option v-for="account in accountOptions" :key="account.id" :value="account.handle">
              @{{ account.handle }}
            </option>
          </select>
          <select v-model="xMonitorStore.filters.market" class="flex-1 rounded-xl border border-border bg-field px-3 py-2.5 text-text">
            <option value="">全部市场</option>
            <option value="cn">A股/国内</option>
            <option value="hk">港股</option>
            <option value="us">美股</option>
          </select>
          <select v-model="xMonitorStore.searchTierFilter" class="flex-1 rounded-xl border border-border bg-field px-3 py-2.5 text-text">
            <option value="">默认层级视图</option>
            <option value="core">仅 core</option>
            <option value="watch">仅 watch</option>
            <option value="muted">仅 muted</option>
          </select>
        </div>

        <input v-model.trim="xMonitorStore.filters.q" class="mt-2 w-full rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="search" placeholder="搜索帖子内容" />

        <div class="mt-5 grid gap-3">
          <div class="flex items-center justify-between gap-2">
            <div>
              <p class="m-0 text-sm font-semibold text-text">账号管理</p>
              <p class="m-0 text-xs text-text-faint">页面直接维护监控账号，配置文件只用于显式导入和导出。</p>
            </div>
            <div class="flex gap-2">
              <button
                class="rounded-full border border-border bg-field px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-60"
                data-role="import-accounts"
                type="button"
                :disabled="xMonitorStore.importExportLoading"
                @click="xMonitorStore.importAccounts()"
              >
                导入
              </button>
              <button
                class="rounded-full border border-border bg-field px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-60"
                data-role="export-accounts"
                type="button"
                :disabled="xMonitorStore.importExportLoading"
                @click="xMonitorStore.exportAccounts()"
              >
                导出
              </button>
            </div>
          </div>

          <p v-if="xMonitorStore.importExportError" class="m-0 text-sm text-danger" data-role="x-import-export-error">
            {{ xMonitorStore.importExportError }}
          </p>
          <p v-if="xMonitorStore.accountMutationError" class="m-0 text-sm text-danger" data-role="x-account-mutation-error">
            {{ xMonitorStore.accountMutationError }}
          </p>

          <form class="grid gap-2 rounded-2xl border border-border bg-panel-stronger p-3" data-role="account-create-form" @submit.prevent="submitCreateAccount">
            <div class="grid gap-2 md:grid-cols-2">
              <input v-model.trim="createForm.handle" data-role="create-handle" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="text" placeholder="@handle" />
              <input v-model.trim="createForm.display_name" data-role="create-display-name" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="text" placeholder="显示名" />
              <select v-model="createForm.market_focus" data-role="create-market" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text">
                <option value="us">美股</option>
                <option value="hk">港股</option>
                <option value="cn">A股/国内</option>
              </select>
              <select v-model="createForm.tier" data-role="create-tier" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text">
                <option value="core">core</option>
                <option value="watch">watch</option>
                <option value="muted">muted</option>
              </select>
              <input v-model="createForm.priority" data-role="create-priority" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="number" placeholder="优先级" />
              <input v-model.trim="createForm.notes" data-role="create-notes" class="rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="text" placeholder="备注" />
            </div>
            <div class="flex justify-end">
              <button
                class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-[14px] py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
                type="submit"
                :disabled="xMonitorStore.accountMutationLoading || !createForm.handle.trim() || !createForm.display_name.trim()"
              >
                新增账号
              </button>
            </div>
          </form>

          <div class="grid gap-2" data-role="account-list">
            <article v-for="account in xMonitorStore.accounts" :key="account.id" class="grid gap-2 rounded-2xl border border-border bg-panel-stronger p-3">
              <div class="flex items-center justify-between gap-2">
                <div class="flex flex-wrap items-center gap-2">
                  <strong>@{{ account.handle }}</strong>
                  <span class="pill" :class="tierTone(account.tier)">{{ account.tier }}</span>
                  <span class="text-text-faint">{{ account.display_name }}</span>
                </div>
                <span class="text-xs text-text-faint">{{ account.source }}</span>
              </div>
              <div class="flex flex-wrap gap-3 text-sm text-text-faint">
                <span>{{ account.market_focus?.toUpperCase() ?? '--' }}</span>
                <span>priority {{ account.priority }}</span>
                <span>{{ account.is_active ? 'active' : 'paused' }}</span>
              </div>
              <p v-if="account.notes" class="m-0 text-sm text-text-soft">{{ account.notes }}</p>
              <div class="flex gap-2">
                <button
                  class="rounded-full border border-border bg-field px-3 py-1.5 text-sm text-text"
                  data-role="toggle-account"
                  type="button"
                  @click="toggleAccount(account)"
                >
                  {{ account.is_active ? '停用' : '启用' }}
                </button>
                <button
                  class="rounded-full border border-[#7f1d1d] bg-[rgba(69,16,16,0.6)] px-3 py-1.5 text-sm text-[#fecaca]"
                  data-role="delete-account"
                  type="button"
                  @click="removeAccount(account.handle)"
                >
                  删除
                </button>
              </div>
            </article>
          </div>
        </div>
      </SectionCard>
    </section>

    <SectionCard title="关键词搜索" subtitle="手动搜索关键词、ticker 或话题，直接查看 twitterapi.io 返回的推文结果">
      <form class="flex items-center gap-2.5" @submit.prevent="xMonitorStore.searchPosts()">
        <input v-model.trim="xMonitorStore.searchQuery" class="flex-1 rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="search" placeholder="输入关键词、ticker 或组合查询" />
        <button
          class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-[14px] py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
          type="submit"
          :disabled="xMonitorStore.searchLoading || !xMonitorStore.searchQuery.trim()"
        >
          {{ xMonitorStore.searchLoading ? '搜索中...' : '执行搜索' }}
        </button>
      </form>

      <LoadingBlock :loading="xMonitorStore.searchLoading" :empty="xMonitorStore.searchResults.length === 0" empty-text="当前没有搜索结果">
        <div class="grid gap-3">
          <article
            v-for="post in xMonitorStore.searchResults"
            :key="xMonitorStore.getTranslationKey(post)"
            class="grid gap-3 rounded-[18px] border border-border bg-panel-stronger p-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <strong>{{ post.account_display_name }}</strong>
                <span class="text-text-faint">@{{ post.account_handle }}</span>
              </div>
              <span class="pill" :class="post.sentiment_label">{{ sentimentText(post.sentiment_label) }}</span>
            </div>
            <p class="m-0 text-text-soft">{{ post.content_text }}</p>
            <div class="flex flex-wrap items-center gap-2.5">
              <button
                class="rounded-full border border-system/25 bg-[rgba(16,31,45,0.92)] px-3 py-1.5 text-[0.82rem] font-semibold text-[#d7f1ff] disabled:cursor-not-allowed disabled:opacity-60"
                data-role="translate-button"
                type="button"
                :disabled="translationState(post).status === 'loading'"
                @click="xMonitorStore.translatePost(post)"
              >
                {{ translationState(post).status === 'loading' ? '翻译中...' : '翻译' }}
              </button>
              <p v-if="translationState(post).status === 'error' && translationState(post).error" class="m-0 text-[0.84rem] text-[#fca5a5]">
                {{ translationState(post).error }}
              </p>
            </div>
            <p v-if="translationState(post).status === 'success' && translationState(post).translated_text" class="m-0 text-[0.84rem] text-[#d9edf8]">
              {{ translationState(post).translated_text }}
            </p>
            <div class="flex flex-wrap gap-2 text-muted">
              <span>{{ formatMarketTime(post.posted_at ?? post.captured_at, post.market) }} {{ getMarketTimezoneLabel(post.market) }}</span>
              <span>{{ post.market.toUpperCase() }}</span>
            </div>
            <div class="flex flex-wrap gap-2 text-muted">
              <span v-if="post.symbols.length > 0">{{ post.symbols.join(' · ') }}</span>
              <span v-else>暂无股票命中</span>
              <a v-if="post.canonical_url" :href="post.canonical_url" target="_blank" rel="noreferrer">打开原帖</a>
            </div>
          </article>
        </div>
      </LoadingBlock>
    </SectionCard>
  </div>
</template>
