<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import { apiClient } from '../api/client';
import type { CalendarEvent, CalendarResponse } from '../types/api';

const router = useRouter();

const loading = ref(true);
const errorMessage = ref<string | null>(null);
const response = ref<CalendarResponse | null>(null);

// 前视窗口天数（含快捷切换）。
const windowDays = ref(30);
const windowOptions = [
  { label: '未来 14 天', value: 14 },
  { label: '未来 30 天', value: 30 },
  { label: '未来 60 天', value: 60 },
  { label: '未来 90 天', value: 90 },
];

const eventTypeLabelMap: Record<string, string> = {
  earnings: '财报',
  ex_dividend: '除息',
};

async function loadCalendar() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const { data } = await apiClient.getCalendar(windowDays.value);
    response.value = data;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '日历加载失败';
    response.value = null;
  } finally {
    loading.value = false;
  }
}

function selectWindow(value: number) {
  if (windowDays.value === value) {
    return;
  }
  windowDays.value = value;
  void loadCalendar();
}

const events = computed<CalendarEvent[]>(() => response.value?.events ?? []);
const skippedCount = computed(() => response.value?.skipped_count ?? 0);

// 按日期分组，后端已按 days_until 升序返回，分组保持自然顺序。
interface CalendarGroup {
  date: string;
  isNear: boolean;
  daysUntil: number;
  events: CalendarEvent[];
}

const groups = computed<CalendarGroup[]>(() => {
  const map = new Map<string, CalendarGroup>();
  for (const event of events.value) {
    let group = map.get(event.date);
    if (!group) {
      group = {
        date: event.date,
        daysUntil: event.days_until,
        isNear: event.days_until <= 3,
        events: [],
      };
      map.set(event.date, group);
    }
    group.events.push(event);
  }
  return [...map.values()].sort((a, b) => a.daysUntil - b.daysUntil);
});

const earningsCount = computed(() => events.value.filter((e) => e.event_type === 'earnings').length);
const dividendCount = computed(() => events.value.filter((e) => e.event_type === 'ex_dividend').length);

function formatDateHeader(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map((part) => Number(part));
  if (!year || !month || !day) {
    return isoDate;
  }
  const weekdayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  const localDate = new Date(year, month - 1, day);
  const weekday = weekdayNames[localDate.getDay()] ?? '';
  return `${month} 月 ${day} 日 · ${weekday}`;
}

function daysUntilLabel(days: number): string {
  if (days <= 0) {
    return '今天';
  }
  if (days === 1) {
    return '明天';
  }
  return `${days} 天后`;
}

function openSymbol(symbol: string) {
  router.push({ name: 'watchlist-detail', params: { symbol } });
}

onMounted(() => {
  void loadCalendar();
});
</script>

<template>
  <div class="grid gap-4" data-role="calendar-view">
    <header
      class="flex flex-col gap-3 rounded-[24px] border border-border bg-[linear-gradient(135deg,rgba(19,27,39,0.96),rgba(10,15,24,0.98))] p-5 xl:flex-row xl:items-end xl:justify-between"
    >
      <div>
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Earnings & Events</p>
        <h1 class="page-title mb-2">财报 / 事件日历</h1>
        <p class="page-subtitle">追踪自选股即将到来的财报日与除息日，临近事件优先高亮。</p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5" data-role="calendar-window-switch">
        <span class="mr-1 text-[11px] uppercase tracking-[0.16em] text-muted">窗口</span>
        <button
          v-for="option in windowOptions"
          :key="option.value"
          type="button"
          class="rounded-full border px-3 py-1.5 text-[11px] font-semibold transition duration-150"
          :class="
            windowDays === option.value
              ? 'border-[#ff9f2f66] bg-[rgba(255,159,47,0.12)] text-[#ffca97]'
              : 'border-border/60 bg-white/[0.02] text-muted hover:bg-white/[0.05] hover:text-text'
          "
          @click="selectWindow(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </header>

    <section
      class="flex flex-wrap items-center gap-2.5 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(135deg,rgba(12,19,31,0.94),rgba(8,14,24,0.98))] px-4 py-3 text-sm"
      data-role="calendar-summary"
    >
      <span class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Overview</span>
      <span class="rounded-full border border-border px-2.5 py-0.5 text-[11px] tracking-[0.14em] text-text">
        财报 {{ earningsCount }}
      </span>
      <span class="rounded-full border border-border px-2.5 py-0.5 text-[11px] tracking-[0.14em] text-text">
        除息 {{ dividendCount }}
      </span>
      <span
        v-if="skippedCount > 0"
        class="rounded-full border border-[rgba(248,113,113,0.28)] px-2.5 py-0.5 text-[11px] tracking-[0.14em] text-[#fecaca]"
        title="部分自选股日历拉取失败，已优雅跳过"
      >
        跳过 {{ skippedCount }}
      </span>
      <span class="ml-auto text-[11px] uppercase tracking-[0.14em] text-text-faint">未来 {{ windowDays }} 天</span>
    </section>

    <p v-if="errorMessage" class="rounded-[14px] border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.06)] px-4 py-3 text-sm text-danger">
      {{ errorMessage }}
    </p>

    <section>
      <LoadingBlock
        :loading="loading"
        :empty="groups.length === 0"
        :skeletonType="'watchlist'"
        :skeletonCount="3"
        empty-text="未来窗口内暂无财报 / 除息事件"
      >
        <div class="grid gap-4" data-role="calendar-groups">
          <article
            v-for="group in groups"
            :key="group.date"
            class="grid gap-2.5 rounded-[20px] border px-4 py-4"
            :class="
              group.isNear
                ? 'calendar-group--near border-[#ff9f2f4d] bg-[linear-gradient(160deg,rgba(35,23,11,0.9),rgba(12,13,10,0.96))]'
                : 'border-border bg-[linear-gradient(180deg,rgba(11,18,28,0.96),rgba(8,14,23,0.98))]'
            "
            :data-role="`calendar-group-${group.date}`"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-baseline gap-2.5">
                <strong class="text-[15px] text-text">{{ formatDateHeader(group.date) }}</strong>
                <span
                  class="text-[11px] uppercase tracking-[0.14em]"
                  :class="group.isNear ? 'text-[#ffca97]' : 'text-text-faint'"
                >
                  {{ daysUntilLabel(group.daysUntil) }}
                </span>
              </div>
              <span
                v-if="group.isNear"
                class="calendar-pulse-dot inline-flex h-2.5 w-2.5 rounded-full bg-[#ff9f2f]"
                aria-hidden="true"
              />
            </div>

            <div class="grid gap-2">
              <button
                v-for="event in group.events"
                :key="`${event.symbol}-${event.event_type}`"
                type="button"
                class="flex items-center justify-between gap-3 rounded-[13px] border border-border/70 bg-white/[0.02] px-3 py-2.5 text-left transition duration-150 hover:-translate-y-px hover:border-system/25 hover:bg-white/[0.05]"
                :data-role="`calendar-event-${event.symbol}`"
                @click="openSymbol(event.symbol)"
              >
                <div class="grid min-w-0 gap-0.5">
                  <div class="flex min-w-0 items-center gap-2">
                    <strong class="truncate text-[13px] text-text">{{ event.display_name ?? event.symbol }}</strong>
                    <span class="shrink-0 text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ event.symbol }}</span>
                  </div>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                  <span
                    class="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]"
                    :class="
                      event.event_type === 'earnings'
                        ? 'border-[#ff9f2f4d] bg-[rgba(255,159,47,0.1)] text-[#ffca97]'
                        : 'border-[#53c2ff40] bg-[rgba(83,194,255,0.08)] text-[#9bd8ff]'
                    "
                  >
                    {{ eventTypeLabelMap[event.event_type] ?? event.event_type }}
                  </span>
                  <span class="text-[11px] font-semibold tabular-nums text-text-soft">
                    {{ daysUntilLabel(event.days_until) }}
                  </span>
                </div>
              </button>
            </div>
          </article>
        </div>
      </LoadingBlock>
    </section>
  </div>
</template>

<style scoped>
/* 临近事件（≤3 天）呼吸高亮。 */
.calendar-group--near {
  animation: calendar-breathe 2.6s ease-in-out infinite;
}

@keyframes calendar-breathe {
  0%,
  100% {
    box-shadow: 0 0 0 rgba(255, 159, 47, 0);
  }
  50% {
    box-shadow: 0 0 22px rgba(255, 159, 47, 0.16);
  }
}

.calendar-pulse-dot {
  animation: calendar-pulse 1.8s ease-in-out infinite;
}

@keyframes calendar-pulse {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@media (prefers-reduced-motion: reduce) {
  .calendar-group--near,
  .calendar-pulse-dot {
    animation: none;
  }
}
</style>
