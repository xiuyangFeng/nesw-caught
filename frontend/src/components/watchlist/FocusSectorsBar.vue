<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { apiClient } from '../../api/client';
import type { FocusSector } from '../../types/api';

// 关注板块：AI 根据自选股推断 + 手动添加 − 手动删除；关注板块的重要新闻会进入每 30 分钟的合并提醒。
const sectors = ref<FocusSector[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const newName = ref('');
const adding = ref(false);
const removingName = ref<string | null>(null);

function sectorTooltip(sector: FocusSector) {
  const origin = sector.source === 'ai' ? 'AI 根据自选股推断' : '手动添加';
  const symbols = sector.symbols ?? [];
  return symbols.length > 0 ? `${origin}：${symbols.join('、')}` : origin;
}

async function load() {
  loading.value = true;
  try {
    const response = await apiClient.getFocusSectors();
    sectors.value = response.data ?? [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '关注板块加载失败';
  } finally {
    loading.value = false;
  }
}

async function addSector() {
  const name = newName.value.trim();
  if (!name || adding.value) {
    return;
  }
  adding.value = true;
  error.value = null;
  try {
    const response = await apiClient.addFocusSector(name);
    sectors.value = response.data ?? [];
    newName.value = '';
  } catch (err) {
    error.value = `添加失败：${err instanceof Error ? err.message : '请稍后再试'}`;
  } finally {
    adding.value = false;
  }
}

async function removeSector(name: string) {
  if (removingName.value) {
    return;
  }
  removingName.value = name;
  error.value = null;
  try {
    await apiClient.removeFocusSector(name);
    await load();
  } catch (err) {
    error.value = `删除失败：${err instanceof Error ? err.message : '请稍后再试'}`;
  } finally {
    removingName.value = null;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <section
    class="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-panel px-4 py-2.5 text-sm"
    data-role="focus-sectors-bar"
  >
    <span class="shrink-0 text-xs font-semibold text-muted">关注板块</span>
    <span
      v-for="sector in sectors"
      :key="sector.name"
      class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs"
      :class="sector.source === 'ai' ? 'border-ai/40 bg-ai/10 text-text' : 'border-border bg-panel-strong text-text'"
      :title="sectorTooltip(sector)"
      data-role="focus-sector-chip"
    >
      <span
        class="text-[9px] font-semibold"
        :class="sector.source === 'ai' ? 'text-ai' : 'text-text-faint'"
        data-role="focus-sector-source"
      >{{ sector.source === 'ai' ? 'AI' : '手动' }}</span>
      {{ sector.name }}
      <button
        type="button"
        class="ml-0.5 leading-none text-text-faint transition hover:text-danger disabled:opacity-50"
        :aria-label="`移除关注板块 ${sector.name}`"
        :disabled="removingName === sector.name"
        data-role="focus-sector-remove"
        @click="removeSector(sector.name)"
      >
        ×
      </button>
    </span>
    <span v-if="!loading && sectors.length === 0" class="text-xs text-text-faint" data-role="focus-sectors-empty">
      AI 会根据自选股自动推断板块，也可以手动添加
    </span>
    <form class="ml-auto flex items-center gap-1.5" @submit.prevent="addSector">
      <input
        v-model="newName"
        type="text"
        placeholder="板块名称"
        class="w-28 rounded-[10px] border border-border bg-black/20 px-2.5 py-1 text-xs text-text outline-none focus:border-system/40"
        data-role="focus-sector-input"
      />
      <button
        type="submit"
        class="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs text-accent transition hover:bg-accent/20 disabled:opacity-50"
        :disabled="adding || !newName.trim()"
        data-role="focus-sector-add"
      >
        添加
      </button>
    </form>
    <p v-if="error" class="m-0 basis-full text-xs text-danger" data-role="focus-sectors-error">{{ error }}</p>
  </section>
</template>
