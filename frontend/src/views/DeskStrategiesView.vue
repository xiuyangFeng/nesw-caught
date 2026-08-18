<script setup lang="ts">
import { onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantFactor, QuantStrategy } from '../types/api';

const DEFAULT_DSL = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
};

const sleeveLabels: Record<string, string> = {
  event_catalyst: '事件/催化',
  trend_flow: '趋势/资金',
  fundamental_revalue: '基本面重估',
};

const name = ref('主力流入趋势');
const dslText = ref(JSON.stringify(DEFAULT_DSL, null, 2));
const strategies = ref<QuantStrategy[]>([]);
const factors = ref<QuantFactor[]>([]);
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

async function loadFactors() {
  try {
    const response = await apiClient.getQuantFactors();
    factors.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '因子注册表加载失败';
  }
}

// 填入一个引用注册表因子的合法 DSL 模板；注册表未加载时兜底为默认因子，保证按钮始终可用。
function fillExample() {
  const factor = factors.value[0] ?? { key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' };
  name.value = `示例·${factor.key}`;
  dslText.value = JSON.stringify(
    {
      sleeve: factor.sleeve,
      horizon: factor.horizon,
      logic: 'and',
      conditions: [{ factor: factor.key, op: '>', value: 0 }],
    },
    null,
    2,
  );
  preview.value = null;
  error.value = null;
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
  void loadFactors();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-strategies-view">
    <header>
      <h1 class="page-title">策略工作台</h1>
      <p class="page-subtitle">条件组合器只能引用因子注册表；探索性策略默认不得晋级。</p>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="Factors" title="因子注册表" subtitle="条件组合器只能引用下列已注册因子，超出注册表会预览报错" data-role="desk-factor-registry">
      <table v-if="factors.length" class="w-full text-left text-sm">
        <thead class="text-muted">
          <tr>
            <th class="py-1 font-normal">因子键</th>
            <th class="py-1 font-normal">所属 Sleeve</th>
            <th class="py-1 font-normal">有效期限</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="factor in factors" :key="factor.key" class="text-text" data-role="desk-factor-row">
            <td class="py-1 font-mono text-xs">{{ factor.key }}</td>
            <td class="py-1">{{ sleeveLabels[factor.sleeve] ?? factor.sleeve }}</td>
            <td class="py-1">{{ factor.horizon }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-sm text-muted" data-role="desk-factor-registry-empty">因子注册表为空，或后端尚未接入。</p>
    </SectionCard>
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
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="desk-strategy-fill-example" @click="fillExample">填入示例</button>
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
      <p v-if="!strategies.length" class="text-sm text-muted" data-role="desk-strategy-empty">
        尚无策略：默认探索性策略将在后端完成种子后自动出现，也可在上方手动保存。
      </p>
      <ul v-else class="grid gap-2 text-sm" data-role="desk-strategy-list">
        <li v-for="item in strategies" :key="item.id">
          {{ item.name }} · {{ item.exploratory ? '探索性' : '正式' }} · {{ item.is_active ? '启用' : '停用' }}
        </li>
      </ul>
    </SectionCard>
  </div>
</template>
