<script setup lang="ts">
import LoadingBlock from '../common/LoadingBlock.vue';
import SectionCard from '../common/SectionCard.vue';
import type { TopicItem } from '../../types/api';
import TopicBoard from './TopicBoard.vue';

defineProps<{
  topics: TopicItem[];
  loading: boolean;
}>();
</script>

<template>
  <SectionCard
    class="h-full"
    eyebrow="Topic Radar"
    title="主题聚合"
    subtitle="按重要度排序，保留股票和情绪入口"
    data-role="dashboard-column-topics"
  >
    <LoadingBlock :loading="loading" :empty="topics.length === 0" :skeletonType="'watchlist'" :skeletonCount="2">
      <div class="dashboard-column-scroller dashboard-topic-column" data-role="dashboard-column-scroller">
        <TopicBoard :topics="topics" />
      </div>
    </LoadingBlock>
  </SectionCard>
</template>

<style scoped>
.dashboard-column-scroller {
  display: grid;
  gap: 10px;
}

@media (min-width: 1280px) {
  .dashboard-column-scroller {
    max-height: clamp(28rem, calc(100vh - 21rem), 40rem);
    overflow-y: auto;
    padding-right: 4px;
  }
}

.dashboard-topic-column :deep(.terminal-surface) {
  border-radius: 16px;
  padding: 12px;
}

.dashboard-topic-column :deep(.terminal-surface strong.text-base) {
  font-size: 14px;
  line-height: 1.35;
}

.dashboard-topic-column :deep(.terminal-surface p.my-3) {
  margin: 8px 0;
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.dashboard-topic-column :deep([data-role='topic-meta']) {
  gap: 8px;
  font-size: 11px;
  line-height: 1.45;
}
</style>
