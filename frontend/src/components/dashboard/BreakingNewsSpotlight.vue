<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
import type { NewsItem } from '../../types/api';
import { getNewsDisplayTimestamp } from '../../utils/time';

const props = defineProps<{
  newsItems: NewsItem[];
}>();

const emit = defineEmits<{
  (event: 'selectNews', id: number): void;
}>();

// 筛选出最近 12 小时内的突发/高价值新闻列表 (限制最多 5 条)
const spotlightItems = computed(() => {
  if (props.newsItems.length === 0) {
    return [];
  }

  const now = Date.now();
  const twelveHoursMs = 12 * 60 * 60 * 1000;

  let recentItems = props.newsItems.filter((item) => {
    const ts = getNewsDisplayTimestamp(item);
    if (!ts) return false;
    const time = new Date(ts).getTime();
    return !Number.isNaN(time) && (now - time) <= twelveHoursMs;
  });

  if (recentItems.length === 0) {
    recentItems = props.newsItems; // 回退到全量数据
  }

  // 1. 优先提取重要度 >= 8.5 的新闻
  const importantItems = recentItems.filter((item) => {
    const score = item.editorial_score ?? 0.0;
    return score >= 8.5;
  });

  if (importantItems.length > 0) {
    return importantItems.slice(0, 5);
  }

  // 2. 如果没有重要度 >= 8.5 的，退而选取情绪鲜明（非中性）的新闻。
  // 列表接口（NewsItemSummary）没有 sentiment_score，只能用 sentiment_label
  // 判定情绪强度，并在同等强度下按 editorial_score 优先。
  const sentimentIntensity = (item: NewsItem) => {
    if (item.sentiment_label === 'positive' || item.sentiment_label === 'negative') {
      return 1;
    }
    if (item.sentiment_label === 'mixed') {
      return 0.5;
    }
    return 0;
  };
  const extremeItems = [...recentItems].sort((left, right) => {
    const intensityDiff = sentimentIntensity(right) - sentimentIntensity(left);
    if (intensityDiff !== 0) {
      return intensityDiff;
    }
    return (right.editorial_score ?? 0.0) - (left.editorial_score ?? 0.0);
  });

  if (extremeItems.length > 0 && sentimentIntensity(extremeItems[0]) >= 0.5) {
    return extremeItems.slice(0, 3);
  }

  // 3. 再没有则返回最新 3 条新闻
  return props.newsItems.slice(0, 3);
});

const currentIndex = ref(0);
const currentNews = computed(() => spotlightItems.value[currentIndex.value] || null);

let timer: any = null;

function startTimer() {
  stopTimer();
  if (spotlightItems.value.length <= 1) return;
  timer = setInterval(() => {
    nextNews();
  }, 5000);
}

function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function nextNews() {
  if (spotlightItems.value.length === 0) return;
  currentIndex.value = (currentIndex.value + 1) % spotlightItems.value.length;
}

function prevNews() {
  if (spotlightItems.value.length === 0) return;
  currentIndex.value =
    (currentIndex.value - 1 + spotlightItems.value.length) % spotlightItems.value.length;
}

watch(spotlightItems, () => {
  currentIndex.value = 0;
  startTimer();
}, { immediate: true });

onMounted(() => {
  startTimer();
});

onUnmounted(() => {
  stopTimer();
});

function handleOpen() {
  if (currentNews.value) {
    emit('selectNews', currentNews.value.id);
  }
}
</script>

<template>
  <div
    v-if="currentNews"
    class="relative rounded-md border border-danger/30 bg-panel px-4 py-2.5 flex items-center justify-between gap-4 transition duration-200 hover:border-danger/50"
    data-role="breaking-news-spotlight"
    @mouseenter="stopTimer"
    @mouseleave="startTimer"
  >
    <!-- 内容淡入淡出滑动切换 -->
    <div class="flex-grow min-w-0">
      <Transition name="slide-fade" mode="out-in">
        <div :key="currentNews.id" class="flex items-center gap-3 min-w-0">
          <!-- 心跳呼吸动效警示点 (双层声纳波纹) -->
          <span class="flex h-3 w-3 relative items-center justify-center shrink-0">
            <!-- 外层波纹 -->
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-danger opacity-40" style="animation-duration: 2s;"></span>
            <!-- 内层波纹 -->
            <span class="animate-ping absolute inline-flex h-[80%] w-[80%] rounded-full bg-danger opacity-60" style="animation-duration: 1.4s;"></span>
            <!-- 核心点 -->
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-danger shadow-[0_0_6px_var(--danger)]"></span>
          </span>

          <span class="text-[10px] font-bold uppercase tracking-[0.2em] bg-danger/10 text-danger px-2 py-0.5 rounded-sm whitespace-nowrap font-mono">
            BREAKING RADAR
          </span>

          <!-- 滚动条标题 -->
          <strong class="text-[13px] font-semibold text-text truncate hover:text-danger transition duration-150 cursor-pointer" @click="handleOpen">
            {{ currentNews.title }}
          </strong>
        </div>
      </Transition>
    </div>

    <!-- 交互操作区 -->
    <div class="flex items-center gap-3 shrink-0">
      <!-- 轮播指示器与切换按键 -->
      <div v-if="spotlightItems.length > 1" class="flex items-center gap-1.5">
        <button
          class="p-1 rounded-full bg-white/[0.03] border border-border/40 text-muted hover:text-text hover:bg-white/[0.08] transition duration-150"
          type="button"
          title="上一条"
          @click.stop="prevNews"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L6.56 8.5l3.22 3.22a.75.75 0 1 1-1.06 1.06L5.5 8.5l3.22-3.22a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd" />
          </svg>
        </button>
        <span class="text-[10px] text-muted tabular-nums min-w-[28px] text-center font-mono">
          {{ currentIndex + 1 }}/{{ spotlightItems.length }}
        </span>
        <button
          class="p-1 rounded-full bg-white/[0.03] border border-border/40 text-muted hover:text-text hover:bg-white/[0.08] transition duration-150"
          type="button"
          title="下一条"
          @click.stop="nextNews"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0L10.5 8.5l-3.22 3.22a.75.75 0 1 1-1.06-1.06L9.44 8.5 6.22 5.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>

      <button
        class="text-[11px] font-bold text-accent hover:text-danger flex items-center gap-1.5 transition duration-150"
        type="button"
        @click="handleOpen"
      >
        <span>即時研判</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
          <path fill-rule="evenodd" d="M2 8a.75.75 0 0 1 .75-.75h8.783L9.03 4.72a.75.75 0 1 1 1.06-1.06l3.75 3.75a.75.75 0 0 1 0 1.06l-3.75 3.75a.75.75 0 1 1-1.06-1.06l2.503-2.503H2.75A.75.75 0 0 1 2 8Z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* 轮播滑动淡入淡出过渡 */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.35s ease;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
