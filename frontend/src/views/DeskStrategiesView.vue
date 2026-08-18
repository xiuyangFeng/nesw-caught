<script setup lang="ts">
import { onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantStrategy } from '../types/api';

const DEFAULT_DSL = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
};

const name = ref('主力流入趋势');
const dslText = ref(JSON.stringify(DEFAULT_DSL, null, 2));
const strategies = ref<QuantStrategy[]>([]);
const preview = ref<{ errors: string[]; hit: boolean } | null>(null);
const error = ref<string | null>(null);
const saving = ref(false);

function parseDsl(): Record<string, unknown> | null {
  try {
    return JSON.parse(dslText.value) as Record<string, unknown>;
  } catch {
    error.value = 'DSL JSON 无法解析';
    return null;
  }
}

async function load() {
  try {
    const response = await apiClient.getQuantStrategies();
    strategies.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '策略列表加载失败';
  }
}

async function handlePreview() {
  const dsl = parseDsl();
  if (!dsl) return;
  try {
    const response = await apiClient.previewQuantStrategy({ name: name.value, dsl, is_active: false });
    preview.value = response.data;
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '预览失败';
  }
}

async function handleSave() {
  const dsl = parseDsl();
  if (!dsl) return;
  saving.value = true;
  try {
    await apiClient.createQuantStrategy({ name: name.value, dsl, is_active: false });
    await load();
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败';
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-strategies-view">
    <header>
      <h1 class="page-title">策略工作台</h1>
      <p class="page-subtitle">条件组合器只能引用因子注册表；探索性策略默认不得晋级。</p>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="DSL" title="编辑与预览">
      <label class="grid gap-1 text-sm">
        <span class="text-muted">名称</span>
        <input v-model="name" class="rounded-md border border-border bg-panel px-3 py-1.5" data-role="desk-strategy-name" />
      </label>
      <textarea
        v-model="dslText"
        class="mt-3 min-h-[180px] w-full rounded-md border border-border bg-panel p-3 font-mono text-xs"
        data-role="desk-strategy-dsl"
      />
      <div class="mt-3 flex flex-wrap gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="desk-strategy-preview" @click="handlePreview">预览</button>
        <button type="button" class="rounded-md border border-accent px-3 py-1.5 text-sm text-accent" :disabled="saving" data-role="desk-strategy-save" @click="handleSave">
          {{ saving ? '保存中…' : '保存为探索性策略' }}
        </button>
      </div>
      <p v-if="preview" class="mt-3 text-sm text-muted" data-role="desk-strategy-preview-result">
        错误 {{ preview.errors.join(', ') || '无' }} · 合成特征命中 {{ preview.hit ? '是' : '否' }}
      </p>
    </SectionCard>
    <SectionCard eyebrow="Saved" title="已保存策略">
      <p v-if="!strategies.length" class="text-sm text-muted">尚无策略。</p>
      <ul v-else class="grid gap-2 text-sm" data-role="desk-strategy-list">
        <li v-for="item in strategies" :key="item.id">
          {{ item.name }} · {{ item.exploratory ? '探索性' : '正式' }} · {{ item.is_active ? '启用' : '停用' }}
        </li>
      </ul>
    </SectionCard>
  </div>
</template>
