<script setup lang="ts">
import type { OpsLlmUsage } from '../../types/api';
import { numberLabel } from './opsFormat';

defineProps<{
  llmUsage: OpsLlmUsage | null;
}>();
</script>

<template>
  <!-- LLM usage -->
  <section class="ops-card" data-role="ops-llm">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Cost</p>
        <h2 class="ops-card-title">LLM 用量 · 近 {{ llmUsage?.window_hours ?? 24 }}h</h2>
      </div>
      <span class="ops-count">{{ numberLabel(llmUsage?.call_count ?? 0) }} 次</span>
    </div>
    <div class="ops-stat-grid">
      <div class="ops-stat">
        <span class="ops-stat-val">{{ numberLabel(llmUsage?.total_tokens ?? 0) }}</span>
        <span class="ops-stat-label">总 tokens</span>
      </div>
      <div class="ops-stat">
        <span class="ops-stat-val">{{ numberLabel(llmUsage?.prompt_tokens ?? 0) }}</span>
        <span class="ops-stat-label">prompt</span>
      </div>
      <div class="ops-stat">
        <span class="ops-stat-val">{{ numberLabel(llmUsage?.completion_tokens ?? 0) }}</span>
        <span class="ops-stat-label">completion</span>
      </div>
    </div>
    <div v-if="llmUsage && llmUsage.models.length > 0" class="mt-3 grid gap-1.5">
      <div
        v-for="model in llmUsage.models"
        :key="model.model_name"
        class="ops-model-row"
      >
        <span class="truncate text-[12px] text-text-soft">{{ model.model_name }}</span>
        <span class="text-[11px] text-muted">{{ numberLabel(model.total_tokens) }} tok · {{ model.call_count }} 次</span>
      </div>
    </div>
    <div v-else class="ops-empty">近 24h 无 LLM 调用</div>
  </section>
</template>

<style scoped>
.ops-card {
  background: var(--panel);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  border-radius: 18px;
  padding: 16px 16px;
  backdrop-filter: blur(12px);
}

.ops-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ops-eyebrow {
  margin: 0 0 2px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #ffb77d;
}

.ops-card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.ops-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 10px;
}

.ops-empty {
  border-radius: 12px;
  border: 1px dashed var(--border);
  padding: 14px;
  text-align: center;
  font-size: 12px;
  color: var(--text-faint);
}

.ops-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.ops-stat {
  display: grid;
  gap: 2px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.025);
  padding: 10px 12px;
}

.ops-stat-val {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.ops-stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-faint);
}

.ops-model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
  padding: 8px 10px;
}
</style>
