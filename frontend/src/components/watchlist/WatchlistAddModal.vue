<script setup lang="ts">
import type { WatchlistCandidate } from '../../types/api';

defineProps<{
  open: boolean;
  query: string;
  matches: WatchlistCandidate[];
  selectedCandidate: WatchlistCandidate | null;
  advancedOpen: boolean;
  alertThreshold: string;
  createLoading: boolean;
  createError: string | null;
}>();

const emit = defineEmits<{
  close: [];
  updateQuery: [value: string];
  selectCandidate: [candidate: WatchlistCandidate];
  toggleAdvanced: [];
  updateAlertThreshold: [value: string];
  submit: [];
}>();
</script>

<template>
  <div
    class="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(3,7,13,0.72)] px-4 py-8"
    :class="open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'"
    :aria-hidden="open ? 'false' : 'true'"
    aria-modal="true"
    data-role="watchlist-add-modal"
    role="dialog"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-4xl rounded-lg border border-border bg-panel p-4 shadow-shell">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-[10px] uppercase tracking-[0.2em] text-accent">Add</p>
          <h2 class="mt-1 text-xl text-text">添加自选</h2>
          <p class="mt-1 text-sm text-text-soft">选中候选后直接加入，需要时再展开高级设置。</p>
        </div>
        <button
          type="button"
          class="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.18em] text-text-faint"
          data-role="watchlist-add-close"
          @click="emit('close')"
        >
          关闭
        </button>
      </div>

      <div class="mt-5 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <section class="rounded-[20px] border border-border/80 bg-black/10 p-4">
          <label class="block text-[10px] uppercase tracking-[0.16em] text-text-faint" for="watchlist-add-search">
            搜索候选
          </label>
          <input
            id="watchlist-add-search"
            :value="query"
            class="mt-2 w-full rounded-xl border border-border bg-field px-3 py-2 text-sm text-text"
            data-role="watchlist-add-search"
            placeholder="输入股票代码、名称或别名"
            @input="emit('updateQuery', ($event.target as HTMLInputElement).value)"
          />
          <div class="mt-3 grid gap-2">
            <button
              v-for="candidate in matches"
              :key="candidate.symbol"
              type="button"
              class="rounded-md border px-3 py-2.5 text-left transition"
              :class="
                selectedCandidate?.symbol === candidate.symbol
                  ? 'border-accent/60 bg-accent/10'
                  : 'border-border/70 bg-panel-strong hover:border-accent/40'
              "
              :data-role="`watchlist-candidate-${candidate.symbol}`"
              @click="emit('selectCandidate', candidate)"
            >
              <strong class="block text-sm text-text">{{ candidate.display_name }}</strong>
              <span class="text-[11px] uppercase tracking-[0.12em] text-text-faint">
                {{ candidate.symbol }} · {{ candidate.market }}
              </span>
            </button>
            <p v-if="query.trim() && matches.length === 0" class="rounded-2xl border border-dashed border-border/70 px-3 py-4 text-sm text-text-soft">
              没有匹配到候选股票
            </p>
          </div>
        </section>

        <section class="rounded-[20px] border border-border/80 bg-[rgba(255,255,255,0.02)] p-4">
          <p class="text-[10px] uppercase tracking-[0.2em] text-accent">Selection</p>
          <div v-if="selectedCandidate" class="mt-3 grid gap-3">
            <div class="rounded-md border border-accent/40 bg-accent/10 p-4">
              <strong class="block text-lg text-text">{{ selectedCandidate.display_name }}</strong>
              <span class="mt-1 block text-[11px] uppercase tracking-[0.14em] text-text-faint" data-role="watchlist-add-selected-symbol">
                {{ selectedCandidate.symbol }} · {{ selectedCandidate.market }}
              </span>
            </div>
            <button
              type="button"
              class="justify-self-start rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.18em] text-text-faint"
              data-role="watchlist-add-advanced-toggle"
              @click="emit('toggleAdvanced')"
            >
              {{ advancedOpen ? '收起高级设置' : '展开高级设置' }}
            </button>
            <div v-if="advancedOpen" class="grid gap-2 rounded-[20px] border border-border/70 bg-black/10 p-4">
              <label class="text-[11px] uppercase tracking-[0.14em] text-text-faint" for="watchlist-add-threshold">
                异动阈值 (%)
              </label>
              <input
                id="watchlist-add-threshold"
                :value="alertThreshold"
                class="w-full rounded-2xl border border-border bg-field px-3 py-2.5 text-sm text-text"
                data-role="watchlist-add-threshold"
                inputmode="decimal"
                placeholder="例如 5"
                @input="emit('updateAlertThreshold', ($event.target as HTMLInputElement).value)"
              />
            </div>
          </div>
          <p v-else class="mt-3 rounded-[20px] border border-dashed border-border/70 px-3 py-6 text-sm text-text-soft">
            先从左侧选中一个候选股票，再决定是否直接添加。
          </p>

          <p v-if="createError" class="mt-4 text-sm text-danger">{{ createError }}</p>

          <div class="mt-6 flex flex-wrap justify-end gap-3">
            <button
              type="button"
              class="rounded-full border border-border px-4 py-2 text-sm text-text-faint"
              @click="emit('close')"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-[#04141a] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="!selectedCandidate || createLoading"
              data-role="watchlist-add-submit"
              @click="emit('submit')"
            >
              {{ createLoading ? '添加中...' : '直接添加' }}
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
