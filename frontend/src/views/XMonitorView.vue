<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import { useXMonitorStore } from '../stores/xMonitorStore';
import { sentimentText } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

const xMonitorStore = useXMonitorStore();

const accountOptions = computed(() => xMonitorStore.accounts.filter((item) => item.is_active));
const bannerTone = computed(() => {
  if (xMonitorStore.health?.enabled === false) return 'warning';
  if (xMonitorStore.health && !xMonitorStore.health.healthy) return 'danger';
  return xMonitorStore.usingMock ? 'warning' : 'default';
});
const bannerTitle = computed(() => {
  if (xMonitorStore.health?.enabled === false) return 'X Monitor 未启用';
  if (xMonitorStore.health && !xMonitorStore.health.configured) return 'twitterapi.io API key 未配置';
  if (xMonitorStore.health && !xMonitorStore.health.healthy) return 'twitterapi.io 当前不可用';
  return xMonitorStore.usingMock ? '已启用 mock 兼容层' : 'X Monitor 已连接到 twitterapi.io';
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
const feedSummaryTitle = computed(() => `当前跟踪 ${xMonitorStore.posts.length} 条帖子，帖子流已同步到最新窗口`);
const feedSummaryDetail = computed(() => {
  const detailParts: string[] = [];
  if (policySummary.value) detailParts.push(policySummary.value);
  const refreshAt = xMonitorStore.lastRefresh?.finished_at ?? xMonitorStore.health?.last_success_at ?? null;
  if (refreshAt) detailParts.push(`最近刷新 ${formatMarketTime(refreshAt, 'us')} ${getMarketTimezoneLabel('us')}`);
  return detailParts.join(' · ');
});

function translationState(post: { account_handle: string; posted_at: string | null; captured_at: string; content_text: string; canonical_url: string | null }) {
  const key = xMonitorStore.getTranslationKey(post);
  return (
    xMonitorStore.translationsByKey[key] ?? {
      status: 'idle',
      translated_text: null,
      error: null,
    }
  );
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
        <h1 class="page-title">X Monitor</h1>
        <p class="page-subtitle">通过 twitterapi.io 拉取关注账号与关键词相关的市场推文，不进入主新闻链路。</p>
      </div>
      <StaleBadge :stale="xMonitorStore.stale" label="X 监控" />
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
    <p v-if="policySummary" class="-mt-1 text-sm text-text-faint">{{ policySummary }}</p>
    <p v-if="xMonitorStore.lastRefresh?.skipped && nextRefreshText" class="-mt-1 text-sm text-text-faint">
      冷却中，下次可刷新：{{ nextRefreshText }}
    </p>

    <section class="grid gap-4 xl:grid-cols-[0.9fr_1.3fr]" data-role="x-monitor-layout">
      <SectionCard title="状态与筛选" subtitle="provider 状态、账号白名单和帖子过滤条件">
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
          <input v-model.trim="xMonitorStore.filters.q" class="flex-1 rounded-xl border border-border bg-field px-3 py-2.5 text-text" type="search" placeholder="搜索帖子内容" />
        </div>

        <div class="mt-4 flex flex-wrap gap-2 text-muted">
          <span v-for="account in accountOptions" :key="account.id" class="pill neutral">
            @{{ account.handle }} · {{ account.display_name }}
          </span>
        </div>
      </SectionCard>

      <SectionCard title="账号监控帖子流" subtitle="保留博主、时间、情绪、股票命中和原帖链接">
        <LoadingBlock :loading="xMonitorStore.loading || xMonitorStore.healthLoading" :empty="xMonitorStore.posts.length === 0" empty-text="当前没有可展示的 X 帖子">
          <div class="mb-3 grid gap-1.5 rounded-[14px] border-l-[3px] border-l-system bg-[linear-gradient(135deg,rgba(15,27,40,0.96),rgba(10,19,31,0.86))] px-4 py-3" data-role="feed-summary">
            <p class="m-0 text-[0.68rem] uppercase tracking-[0.14em] text-system">Monitor Status</p>
            <p class="m-0 text-[1.05rem] leading-[1.45]" data-role="feed-summary-title">{{ feedSummaryTitle }}</p>
            <p class="m-0 text-[0.8rem] leading-[1.45] text-text-faint" data-role="feed-summary-detail">{{ feedSummaryDetail }}</p>
          </div>
          <div
            class="grid rounded-2xl border border-system/10 bg-[rgba(10,18,29,0.58)] shell:max-h-[clamp(420px,56vh,720px)] shell:overflow-y-auto"
            data-role="post-feed"
          >
            <article
              v-for="post in xMonitorStore.posts"
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
