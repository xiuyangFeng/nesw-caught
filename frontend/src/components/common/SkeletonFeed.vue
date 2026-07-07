<script setup lang="ts">
defineProps<{
  type?: 'news' | 'dashboard' | 'watchlist' | 'detail';
  count?: number;
}>();
</script>

<template>
  <div class="skeleton-wrapper">
    <!-- 新闻列表骨架屏 -->
    <template v-if="type === 'news' || !type">
      <div
        v-for="i in (count || 4)"
        :key="i"
        class="skeleton-card news-skeleton"
      >
        <div class="skeleton-line title-line shimmer"></div>
        <div class="skeleton-line desc-line-1 shimmer"></div>
        <div class="skeleton-line desc-line-2 shimmer"></div>
        <div class="skeleton-footer">
          <div class="skeleton-pill shimmer"></div>
          <div class="skeleton-pill shimmer"></div>
          <div class="skeleton-pill small shimmer"></div>
        </div>
      </div>
    </template>

    <!-- 仪表盘板块骨架屏 -->
    <template v-elif="type === 'dashboard'">
      <div class="dashboard-skeleton-grid">
        <div class="skeleton-card dash-metric shimmer"></div>
        <div class="skeleton-card dash-metric shimmer"></div>
        <div class="skeleton-card dash-metric shimmer"></div>
        <div class="skeleton-card dash-metric shimmer"></div>
      </div>
      <div class="dashboard-panels">
        <div class="skeleton-card dash-panel-large shimmer"></div>
        <div class="skeleton-card dash-panel-small shimmer"></div>
      </div>
    </template>

    <!-- 自选股列表骨架屏 -->
    <template v-elif="type === 'watchlist'">
      <div
        v-for="i in (count || 3)"
        :key="i"
        class="skeleton-card watchlist-skeleton"
      >
        <div class="watchlist-header">
          <div class="skeleton-pill shimmer"></div>
          <div class="skeleton-line short-line shimmer"></div>
        </div>
        <div class="watchlist-body">
          <div class="skeleton-line shimmer"></div>
          <div class="skeleton-line shimmer"></div>
        </div>
      </div>
    </template>

    <!-- 新闻详情骨架屏 -->
    <template v-elif="type === 'detail'">
      <div class="skeleton-card detail-skeleton">
        <div class="skeleton-line title-line shimmer"></div>
        <div class="skeleton-footer">
          <div class="skeleton-pill shimmer"></div>
          <div class="skeleton-pill shimmer"></div>
        </div>
        <div class="divider"></div>
        <div class="skeleton-line desc-line-1 shimmer"></div>
        <div class="skeleton-line desc-line-2 shimmer"></div>
        <div class="skeleton-line desc-line-1 shimmer"></div>
        <div class="skeleton-line desc-line-2 shimmer"></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.skeleton-wrapper {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.skeleton-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 18px;
  position: relative;
  overflow: hidden;
}

/* 呼吸扫光 Shimmer 动画 */
.shimmer::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  transform: translateX(-100%);
  background-image: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.03) 20%,
    rgba(255, 255, 255, 0.08) 60%,
    rgba(255, 255, 255, 0) 100%
  );
  animation: shimmer 1.6s infinite;
}

@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}

.skeleton-line {
  height: 14px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
}

.title-line {
  height: 20px;
  width: 70%;
  margin-bottom: 20px;
}

.desc-line-1 {
  width: 95%;
}

.desc-line-2 {
  width: 85%;
}

.short-line {
  width: 40%;
}

.skeleton-footer {
  display: flex;
  gap: 8px;
  margin-top: 18px;
}

.skeleton-pill {
  height: 24px;
  width: 80px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 99px;
  position: relative;
  overflow: hidden;
}

.skeleton-pill.small {
  width: 50px;
}

/* 仪表盘骨架屏专用样式 */
.dashboard-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.dash-metric {
  height: 96px;
}

.dashboard-panels {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .dashboard-panels {
    grid-template-columns: 1fr;
  }
}

.dash-panel-large {
  height: 320px;
}

.dash-panel-small {
  height: 320px;
}

/* 自选股骨架屏专用样式 */
.watchlist-skeleton {
  padding: 16px;
}

.watchlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.watchlist-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 16px 0;
}
</style>
