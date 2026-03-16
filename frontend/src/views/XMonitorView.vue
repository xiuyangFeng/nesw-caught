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
  if (xMonitorStore.health && !xMonitorStore.health.bridge_healthy) {
    return 'danger';
  }
  return xMonitorStore.usingMock ? 'warning' : 'default';
});
const bannerTitle = computed(() => {
  if (xMonitorStore.health?.enabled === false) {
    return 'X Monitor 未启用';
  }
  if (xMonitorStore.health && !xMonitorStore.health.bridge_healthy) {
    return 'grok-bridge 当前不可用';
  }
  return xMonitorStore.usingMock ? '已启用 mock 兼容层' : 'X Monitor 已连接到独立接口';
});
const bannerDetail = computed(() => {
  if (!xMonitorStore.health) {
    return '健康状态加载中。';
  }
  return `桥接状态：${xMonitorStore.health.bridge_status}；最近成功：${
    xMonitorStore.health.last_success_at ? formatMarketTime(xMonitorStore.health.last_success_at, 'us') : '--'
  } ${getMarketTimezoneLabel('us')}`;
});

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
        <p class="page-subtitle">用 grok-bridge 补充关注博主的市场相关 X 动态，不进入主新闻链路。</p>
      </div>
      <StaleBadge :stale="xMonitorStore.stale" label="X 监控" />
    </header>

    <StatusBanner :title="bannerTitle" :tone="bannerTone" :detail="bannerDetail">
      <button class="refresh-button" type="button" :disabled="xMonitorStore.refreshLoading" @click="xMonitorStore.refreshPosts()">
        {{ xMonitorStore.refreshLoading ? '刷新中...' : '手动刷新' }}
      </button>
    </StatusBanner>

    <section class="layout">
      <SectionCard title="状态与筛选" subtitle="桥接状态、账号白名单和帖子过滤条件">
        <div class="health-grid">
          <div class="metric">
            <span class="metric-label">模块</span>
            <strong>{{ xMonitorStore.health?.enabled ? '已启用' : '未启用' }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">桥接</span>
            <strong>{{ xMonitorStore.health?.bridge_healthy ? '健康' : '异常' }}</strong>
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

      <SectionCard title="帖子流" subtitle="保留博主、时间、情绪、股票命中和原帖链接">
        <LoadingBlock :loading="xMonitorStore.loading || xMonitorStore.healthLoading" :empty="xMonitorStore.posts.length === 0" empty-text="当前没有可展示的 X 帖子">
          <div class="post-list">
            <article v-for="post in xMonitorStore.posts" :key="post.id" class="post-card">
              <div class="post-head">
                <div>
                  <strong>{{ post.account_display_name }}</strong>
                  <span class="subtle">@{{ post.account_handle }}</span>
                </div>
                <span class="pill" :class="post.sentiment_label">{{ sentimentText(post.sentiment_label) }}</span>
              </div>
              <p class="post-body">{{ post.content_text }}</p>
              <div class="meta-row">
                <span>
                  {{ formatMarketTime(post.posted_at ?? post.captured_at, post.market) }}
                  {{ getMarketTimezoneLabel(post.market) }}
                </span>
                <span>相关度 {{ post.relevance_score?.toFixed(2) ?? '--' }}</span>
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
    </section>
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
  background: linear-gradient(135deg, #1453a3, #1e7acb);
  cursor: pointer;
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
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border);
  display: grid;
  gap: 4px;
}

.metric-label,
.subtle {
  color: var(--muted);
}

.filters {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.filters select,
.filters input {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fffdf8;
  padding: 10px 12px;
}

.account-list,
.meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
  color: var(--muted);
}

.post-list {
  display: grid;
  gap: 12px;
}

.post-card {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.65);
  display: grid;
  gap: 12px;
}

.post-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.post-body {
  margin: 0;
  line-height: 1.55;
}
</style>
