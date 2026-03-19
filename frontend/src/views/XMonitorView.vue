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
  if (xMonitorStore.health?.enabled === false) {
    return 'warning';
  }
  if (xMonitorStore.health && !xMonitorStore.health.healthy) {
    return 'danger';
  }
  return xMonitorStore.usingMock ? 'warning' : 'default';
});
const bannerTitle = computed(() => {
  if (xMonitorStore.health?.enabled === false) {
    return 'X Monitor 未启用';
  }
  if (xMonitorStore.health && !xMonitorStore.health.configured) {
    return 'twitterapi.io API key 未配置';
  }
  if (xMonitorStore.health && !xMonitorStore.health.healthy) {
    return 'twitterapi.io 当前不可用';
  }
  return xMonitorStore.usingMock ? '已启用 mock 兼容层' : 'X Monitor 已连接到 twitterapi.io';
});
const bannerDetail = computed(() => {
  if (!xMonitorStore.health) {
    return '健康状态加载中。';
  }
  return `数据源状态：${xMonitorStore.health.status}；最近成功：${
    xMonitorStore.health.last_success_at ? formatMarketTime(xMonitorStore.health.last_success_at, 'us') : '--'
  } ${getMarketTimezoneLabel('us')}`;
});
const nextRefreshText = computed(() => {
  const nextRefreshAt = xMonitorStore.lastRefresh?.next_refresh_at;
  if (!nextRefreshAt) {
    return null;
  }
  return `${formatMarketTime(nextRefreshAt, 'us')} ${getMarketTimezoneLabel('us')}`;
});
const policySummary = computed(() => {
  if (!xMonitorStore.health) {
    return null;
  }
  return `请求节流 ${xMonitorStore.health.min_interval_seconds} 秒/次 · 账号刷新冷却 ${xMonitorStore.health.refresh_cooldown_hours} 小时`;
});
const feedSummaryTitle = computed(() => {
  const count = xMonitorStore.posts.length;
  return `当前跟踪 ${count} 条帖子，帖子流已同步到最新窗口`;
});
const feedSummaryDetail = computed(() => {
  const detailParts: string[] = [];
  if (policySummary.value) {
    detailParts.push(policySummary.value);
  }
  const refreshAt =
    xMonitorStore.lastRefresh?.finished_at ??
    xMonitorStore.health?.last_success_at ??
    null;
  if (refreshAt) {
    detailParts.push(`最近刷新 ${formatMarketTime(refreshAt, 'us')} ${getMarketTimezoneLabel('us')}`);
  }
  return detailParts.join(' · ');
});

function translationState(post: { account_handle: string; posted_at: string | null; captured_at: string; content_text: string; canonical_url: string | null }) {
  const key = xMonitorStore.getTranslationKey(post);
  return xMonitorStore.translationsByKey[key] ?? {
    status: 'idle',
    translated_text: null,
    error: null,
  };
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
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">X Monitor</h1>
        <p class="page-subtitle">通过 twitterapi.io 拉取关注账号与关键词相关的市场推文，不进入主新闻链路。</p>
      </div>
      <StaleBadge :stale="xMonitorStore.stale" label="X 监控" />
    </header>

    <StatusBanner :title="bannerTitle" :tone="bannerTone" :detail="bannerDetail">
      <button class="refresh-button" type="button" :disabled="xMonitorStore.refreshLoading" @click="xMonitorStore.refreshPosts()">
        {{ xMonitorStore.refreshLoading ? '刷新中...' : '手动刷新' }}
      </button>
    </StatusBanner>
    <p v-if="policySummary" class="policy-caption">{{ policySummary }}</p>
    <p v-if="xMonitorStore.lastRefresh?.skipped && nextRefreshText" class="cooldown-note">
      冷却中，下次可刷新：{{ nextRefreshText }}
    </p>

    <section class="layout">
      <SectionCard title="状态与筛选" subtitle="provider 状态、账号白名单和帖子过滤条件">
        <div class="health-grid">
          <div class="metric">
            <span class="metric-label">模块</span>
            <strong>{{ xMonitorStore.health?.enabled ? '已启用' : '未启用' }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">Provider</span>
            <strong>{{ xMonitorStore.health?.healthy ? '健康' : '异常' }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">最近刷新</span>
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

        <div class="filters">
          <select v-model="xMonitorStore.filters.account_handle">
            <option value="">全部博主</option>
            <option v-for="account in accountOptions" :key="account.id" :value="account.handle">
              @{{ account.handle }}
            </option>
          </select>
          <select v-model="xMonitorStore.filters.market">
            <option value="">全部市场</option>
            <option value="cn">A股/国内</option>
            <option value="hk">港股</option>
            <option value="us">美股</option>
          </select>
          <input v-model.trim="xMonitorStore.filters.q" type="search" placeholder="搜索帖子内容" />
        </div>

        <div class="account-list">
          <span v-for="account in accountOptions" :key="account.id" class="pill neutral">
            @{{ account.handle }} · {{ account.display_name }}
          </span>
        </div>
      </SectionCard>

      <SectionCard title="账号监控帖子流" subtitle="保留博主、时间、情绪、股票命中和原帖链接">
        <LoadingBlock :loading="xMonitorStore.loading || xMonitorStore.healthLoading" :empty="xMonitorStore.posts.length === 0" empty-text="当前没有可展示的 X 帖子">
          <div class="feed-summary">
            <p class="feed-summary-kicker">Monitor Status</p>
            <p class="feed-summary-title">{{ feedSummaryTitle }}</p>
            <p class="feed-summary-detail">{{ feedSummaryDetail }}</p>
          </div>
          <div class="post-feed">
            <article v-for="post in xMonitorStore.posts" :key="post.id" class="post-list-item">
              <div class="post-head compact">
                <div class="post-identity">
                  <strong>{{ post.account_display_name }}</strong>
                  <span class="subtle">@{{ post.account_handle }}</span>
                  <span class="subtle">{{ formatMarketTime(post.posted_at ?? post.captured_at, post.market) }} {{ getMarketTimezoneLabel(post.market) }}</span>
                  <span class="subtle">{{ post.market.toUpperCase() }}</span>
                </div>
                <span class="pill" :class="post.sentiment_label">{{ sentimentText(post.sentiment_label) }}</span>
              </div>
              <p class="post-body">{{ post.content_text }}</p>
              <div class="translation-row">
                <button
                  class="translate-button"
                  type="button"
                  :disabled="translationState(post).status === 'loading'"
                  @click="xMonitorStore.translatePost(post)"
                >
                  {{ translationState(post).status === 'loading' ? '翻译中...' : '翻译' }}
                </button>
                <p v-if="translationState(post).status === 'error' && translationState(post).error" class="translation-error">
                  {{ translationState(post).error }}
                </p>
              </div>
              <p
                v-if="translationState(post).status === 'success' && translationState(post).translated_text"
                class="translation-text"
              >
                {{ translationState(post).translated_text }}
              </p>
              <div class="meta-row compact">
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
      <form class="search-form" @submit.prevent="xMonitorStore.searchPosts()">
        <input v-model.trim="xMonitorStore.searchQuery" type="search" placeholder="输入关键词、ticker 或组合查询" />
        <button class="refresh-button" type="submit" :disabled="xMonitorStore.searchLoading || !xMonitorStore.searchQuery.trim()">
          {{ xMonitorStore.searchLoading ? '搜索中...' : '执行搜索' }}
        </button>
      </form>

      <LoadingBlock :loading="xMonitorStore.searchLoading" :empty="xMonitorStore.searchResults.length === 0" empty-text="当前没有搜索结果">
        <div class="post-list">
          <article v-for="post in xMonitorStore.searchResults" :key="xMonitorStore.getTranslationKey(post)" class="post-card">
            <div class="post-head">
              <div>
                <strong>{{ post.account_display_name }}</strong>
                <span class="subtle">@{{ post.account_handle }}</span>
              </div>
              <span class="pill" :class="post.sentiment_label">{{ sentimentText(post.sentiment_label) }}</span>
            </div>
            <p class="post-body">{{ post.content_text }}</p>
            <div class="translation-row">
              <button
                class="translate-button"
                type="button"
                :disabled="translationState(post).status === 'loading'"
                @click="xMonitorStore.translatePost(post)"
              >
                {{ translationState(post).status === 'loading' ? '翻译中...' : '翻译' }}
              </button>
              <p v-if="translationState(post).status === 'error' && translationState(post).error" class="translation-error">
                {{ translationState(post).error }}
              </p>
            </div>
            <p
              v-if="translationState(post).status === 'success' && translationState(post).translated_text"
              class="translation-text"
            >
              {{ translationState(post).translated_text }}
            </p>
            <div class="meta-row">
              <span>
                {{ formatMarketTime(post.posted_at ?? post.captured_at, post.market) }}
                {{ getMarketTimezoneLabel(post.market) }}
              </span>
              <span>{{ post.market.toUpperCase() }}</span>
            </div>
            <div class="meta-row">
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

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.layout {
  display: grid;
  grid-template-columns: 0.9fr 1.3fr;
  gap: 16px;
  align-items: start;
}

.refresh-button {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  font: inherit;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.refresh-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(58, 169, 245, 0.24);
}

.refresh-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.metric {
  border-radius: 16px;
  padding: 14px;
  background: var(--panel-stronger);
  border: 1px solid var(--border);
  display: grid;
  gap: 4px;
  transition: border-color 160ms ease, transform 160ms ease;
}

.metric:hover {
  border-color: rgba(125, 211, 252, 0.2);
  transform: translateY(-1px);
}

.metric-label,
.subtle {
  color: var(--text-faint);
}

.filters {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.search-form {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filters select,
.filters input,
.search-form input {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--field-bg);
  padding: 10px 12px;
  color: var(--text);
  flex: 1;
}

.account-list,
.meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
  color: var(--muted);
}

.policy-caption,
.cooldown-note {
  margin: -4px 0 0;
  font-size: 0.86rem;
  color: var(--text-faint);
}

.post-list {
  display: grid;
  gap: 12px;
}

.post-card {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid var(--border);
  background: var(--panel-stronger);
  display: grid;
  gap: 12px;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.post-card:hover {
  border-color: rgba(125, 211, 252, 0.2);
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(2, 6, 12, 0.22);
}

.feed-summary {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  padding: 14px 16px;
  border-left: 3px solid rgba(56, 189, 248, 0.9);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(15, 27, 40, 0.96), rgba(10, 19, 31, 0.86));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.feed-summary-kicker {
  margin: 0;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #7dd3fc;
}

.feed-summary-title,
.feed-summary-detail {
  margin: 0;
}

.feed-summary-title {
  font-size: 1.05rem;
  line-height: 1.45;
}

.feed-summary-detail {
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--text-faint);
}

.post-feed {
  display: grid;
  max-height: clamp(420px, 56vh, 720px);
  overflow-y: auto;
  border: 1px solid rgba(125, 211, 252, 0.1);
  border-radius: 16px;
  background: rgba(10, 18, 29, 0.58);
}

.post-list-item {
  padding: 12px 14px;
  display: grid;
  gap: 8px;
  border-bottom: 1px solid rgba(125, 211, 252, 0.08);
}

.post-list-item:last-child {
  border-bottom: none;
}

.post-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.post-head.compact {
  align-items: center;
}

.post-identity {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}

.post-body {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.45;
  color: var(--text-soft);
}

.meta-row.compact {
  margin-top: 0;
  font-size: 0.82rem;
}

.translation-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.translate-button {
  border: 1px solid rgba(125, 211, 252, 0.22);
  border-radius: 999px;
  padding: 6px 12px;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  color: #d7f1ff;
  background: rgba(16, 31, 45, 0.92);
  cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, opacity 160ms ease;
}

.translate-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.42);
}

.translate-button:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.translation-text,
.translation-error {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.5;
}

.translation-text {
  color: #d9edf8;
}

.translation-error {
  color: #fca5a5;
}

@media (max-width: 1024px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .post-feed {
    max-height: none;
  }
}
</style>
