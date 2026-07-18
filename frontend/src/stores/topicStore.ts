import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { TopicDetail, TopicItem } from '../types/api';
import { isStale } from '../utils/time';

export const useTopicStore = defineStore('topicStore', () => {
  const topics = ref<TopicItem[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const detailMap = ref<Record<number, TopicDetail | null>>({});
  const detailLoading = ref(false);

  const topTopics = computed(() => [...topics.value].sort((a, b) => b.importance_score - a.importance_score).slice(0, 6));
  const stale = computed(() => isStale(lastLoadedAt.value, 10));

  async function loadTopics() {
    loading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getTopics();
      topics.value = response.data;
      usingMock.value = response.degraded;
      lastLoadedAt.value = new Date().toISOString();
    } catch (err) {
      error.value = err instanceof Error ? err.message : '话题加载失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  function upsertTopic(topic: TopicItem) {
    const index = topics.value.findIndex((candidate) => candidate.id === topic.id);
    if (index >= 0) {
      topics.value.splice(index, 1, topic);
    } else {
      topics.value.unshift(topic);
    }
    lastLoadedAt.value = new Date().toISOString();
  }

  async function loadDetail(id: number) {
    detailLoading.value = true;
    const response = await apiClient.getTopicDetail(id);
    detailMap.value[id] = response.data;
    usingMock.value = usingMock.value || response.degraded;
    detailLoading.value = false;
  }

  return {
    topics,
    detailMap,
    loading,
    error,
    detailLoading,
    usingMock,
    lastLoadedAt,
    topTopics,
    stale,
    loadTopics,
    loadDetail,
    upsertTopic,
  };
});
