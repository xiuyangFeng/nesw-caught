<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import { useMarketOverviewStore } from '../../stores/marketOverviewStore';
import type { MarketIndexConfig, MarketIndexKind, MarketOverviewMarketKey } from '../../types/api';

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

const store = useMarketOverviewStore();

const MARKET_OPTIONS: Array<{ value: MarketOverviewMarketKey; label: string }> = [
  { value: 'us', label: '美股' },
  { value: 'cn', label: 'A股' },
  { value: 'kr', label: '韩国' },
  { value: 'jp', label: '日本' },
  { value: 'eu', label: '欧洲' },
];

const KIND_OPTIONS: Array<{ value: MarketIndexKind; label: string }> = [
  { value: 'index', label: '指数' },
  { value: 'etf', label: '板块代理 ETF' },
];

function marketLabel(market: string) {
  return MARKET_OPTIONS.find((option) => option.value === market)?.label ?? market;
}

// 打开弹窗时拉取最新配置(含 disabled 项)。
watch(
  () => props.open,
  (open) => {
    if (open) {
      void store.loadIndexConfig();
    }
  },
  { immediate: true },
);

const groupedConfigs = computed(() => {
  const knownMarkets = new Set<string>(MARKET_OPTIONS.map((option) => option.value));
  // 后端 schema 中 market 为普通 string,分组键统一按 string 处理,
  // 契约外市场值走下方 extras 兜底展示。
  const groups: Array<{ market: string; label: string; items: MarketIndexConfig[] }> = MARKET_OPTIONS.map((option) => ({
    market: option.value,
    label: option.label,
    items: store.indexConfigs.filter((config) => config.market === option.value),
  })).filter((group) => group.items.length > 0);
  // 兜底:契约外的市场值也展示出来,避免配置"消失"。
  const extras = store.indexConfigs.filter((config) => !knownMarkets.has(config.market));
  if (extras.length > 0) {
    groups.push({ market: extras[0].market, label: extras[0].market, items: extras });
  }
  return groups;
});

// ---------------------------------------------------------------------------
// 行内编辑(名称 / 排序):草稿按配置 id 保存,点"保存"才 PATCH。
// PATCH 契约不允许改 symbol / market,故这两列只读展示。
// ---------------------------------------------------------------------------
const drafts = reactive<Record<number, { display_name: string; sort_order: string }>>({});

function draftFor(config: MarketIndexConfig) {
  if (!drafts[config.id]) {
    drafts[config.id] = { display_name: config.display_name, sort_order: String(config.sort_order) };
  }
  return drafts[config.id];
}

async function saveRow(config: MarketIndexConfig) {
  const draft = draftFor(config);
  const sortOrder = Number(draft.sort_order);
  try {
    await store.updateIndexConfig(config.id, {
      display_name: draft.display_name.trim() || config.display_name,
      sort_order: Number.isFinite(sortOrder) ? sortOrder : config.sort_order,
    });
    delete drafts[config.id];
  } catch {
    // 失败原因由 store.configError 展示,弹窗保持打开。
  }
}

async function toggleEnabled(config: MarketIndexConfig) {
  try {
    await store.updateIndexConfig(config.id, { enabled: !config.enabled });
  } catch {
  }
}

async function removeRow(config: MarketIndexConfig) {
  if (!window.confirm(`确认删除 ${config.display_name}(${config.symbol}) 吗?`)) {
    return;
  }
  try {
    await store.deleteIndexConfig(config.id);
    delete drafts[config.id];
  } catch {
  }
}

// ---------------------------------------------------------------------------
// 底部新增表单
// ---------------------------------------------------------------------------
const newMarket = ref<MarketOverviewMarketKey>('us');
const newSymbol = ref('');
const newName = ref('');
const newKind = ref<MarketIndexKind>('index');
const addError = ref<string | null>(null);

async function submitAdd() {
  addError.value = null;
  const symbol = newSymbol.value.trim();
  const displayName = newName.value.trim();
  if (!symbol) {
    addError.value = '请填写指数代码(symbol)';
    return;
  }
  if (!displayName) {
    addError.value = '请填写展示名称';
    return;
  }
  try {
    await store.createIndexConfig({
      symbol,
      market: newMarket.value,
      display_name: displayName,
      kind: newKind.value,
    });
    newSymbol.value = '';
    newName.value = '';
  } catch {
    // store.configError 已承载失败原因。
  }
}
</script>

<template>
  <div
    class="fixed inset-0 z-40 flex items-center justify-center bg-[color-mix(in_srgb,var(--bg)_72%,transparent)] px-4 py-8"
    :class="open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'"
    :aria-hidden="open ? 'false' : 'true'"
    aria-modal="true"
    data-role="market-index-config-modal"
    role="dialog"
    @click.self="emit('close')"
  >
    <div class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-border bg-panel p-4 shadow-shell">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-[10px] uppercase tracking-[0.2em] text-accent">Index Config</p>
          <h2 class="mt-1 text-xl text-text">市场指数配置</h2>
          <p class="mt-1 text-sm text-text-soft">增删各市场展示指数与板块代理 ETF,保存后总览自动刷新。</p>
        </div>
        <button
          type="button"
          class="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.18em] text-text-faint"
          data-role="market-index-config-close"
          @click="emit('close')"
        >
          关闭
        </button>
      </div>

      <p v-if="store.configError" class="mt-3 rounded-[12px] border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" data-role="config-store-error">
        {{ store.configError }}
      </p>

      <!-- 按市场分组的配置表 -->
      <div class="mt-4 grid gap-4">
        <section v-for="group in groupedConfigs" :key="group.market" class="rounded-[16px] border border-border/80 bg-black/10 p-3" :data-role="`config-group-${group.market}`">
          <p class="mb-2 text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ group.label }} · {{ group.market }}</p>
          <div class="grid gap-2">
            <div
              v-for="config in group.items"
              :key="config.id"
              class="grid grid-cols-[auto_minmax(0,1fr)_auto_auto_auto_auto] items-center gap-2 rounded-[12px] border border-border/60 bg-panel px-2.5 py-2"
              :data-role="`config-row-${config.id}`"
            >
              <!-- 启用开关 -->
              <button
                type="button"
                class="relative h-5 w-9 shrink-0 rounded-full transition"
                :class="config.enabled ? 'bg-accent' : 'bg-white/15'"
                :aria-pressed="config.enabled"
                :data-role="`config-toggle-${config.id}`"
                :title="config.enabled ? '点击禁用' : '点击启用'"
                @click="toggleEnabled(config)"
              >
                <span
                  class="absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all"
                  :class="config.enabled ? 'left-[18px]' : 'left-0.5'"
                ></span>
              </button>
              <div class="grid min-w-0 gap-0.5">
                <input
                  :value="draftFor(config).display_name"
                  class="w-full rounded-[8px] border border-border bg-field px-2 py-1 text-[13px] text-text"
                  :data-role="`config-name-input-${config.id}`"
                  @input="draftFor(config).display_name = ($event.target as HTMLInputElement).value"
                />
                <span class="truncate font-mono text-[10px] uppercase tracking-[0.12em] text-text-faint">
                  {{ config.symbol }} · {{ config.kind }}
                </span>
              </div>
              <input
                :value="draftFor(config).sort_order"
                class="w-16 rounded-[8px] border border-border bg-field px-2 py-1 text-[13px] text-text"
                inputmode="numeric"
                title="排序值(同市场内越小越靠前)"
                :data-role="`config-sort-input-${config.id}`"
                @input="draftFor(config).sort_order = ($event.target as HTMLInputElement).value"
              />
              <button
                type="button"
                class="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-[11px] text-accent transition hover:bg-accent/20 disabled:opacity-60"
                :disabled="store.configSaving"
                :data-role="`config-save-${config.id}`"
                @click="saveRow(config)"
              >
                保存
              </button>
              <button
                type="button"
                class="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-faint transition hover:bg-danger/20 hover:text-danger"
                :data-role="`config-delete-${config.id}`"
                title="删除该配置"
                @click="removeRow(config)"
              >
                ×
              </button>
            </div>
          </div>
        </section>
        <p v-if="groupedConfigs.length === 0" class="rounded-[16px] border border-dashed border-border/70 px-3 py-4 text-sm text-text-soft">
          尚无指数配置,可在下方新增。
        </p>
      </div>

      <!-- 底部新增表单 -->
      <section class="mt-4 rounded-[16px] border border-border/80 bg-panel-soft p-4" data-role="config-add-form">
        <p class="text-[10px] uppercase tracking-[0.2em] text-accent">Add</p>
        <div class="mt-3 grid gap-2 sm:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)_auto_auto] sm:items-center">
          <select
            v-model="newMarket"
            class="rounded-[10px] border border-border bg-field px-2.5 py-2 text-sm text-text"
            data-role="config-add-market"
          >
            <option v-for="option in MARKET_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <input
            v-model="newSymbol"
            class="rounded-[10px] border border-border bg-field px-3 py-2 text-sm text-text"
            placeholder="Yahoo 代码,如 ^GSPC / 000300.SS"
            data-role="config-add-symbol"
          />
          <input
            v-model="newName"
            class="rounded-[10px] border border-border bg-field px-3 py-2 text-sm text-text"
            placeholder="展示名称,如 标普500"
            data-role="config-add-name"
          />
          <select
            v-model="newKind"
            class="rounded-[10px] border border-border bg-field px-2.5 py-2 text-sm text-text"
            data-role="config-add-kind"
          >
            <option v-for="option in KIND_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <button
            type="button"
            class="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-[var(--bg)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="store.configSaving"
            data-role="config-add-submit"
            @click="submitAdd"
          >
            {{ store.configSaving ? '保存中…' : '新增' }}
          </button>
        </div>
        <p v-if="addError" class="mt-2 text-sm text-danger" data-role="config-add-error">{{ addError }}</p>
      </section>
    </div>
  </div>
</template>
