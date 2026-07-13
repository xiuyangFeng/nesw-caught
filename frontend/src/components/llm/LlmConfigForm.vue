<script setup lang="ts">
import { computed, reactive } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { useLlmStore } from '../../stores/llmStore';
import { useToastStore } from '../../stores/toastStore';
import type { LLMConfigSummary } from '../../types/api';

const llmStore = useLlmStore();
const toastStore = useToastStore();

const formState = reactive({
  id: null as number | null,
  provider_name: '',
  display_name: '',
  base_url: '',
  model_name: '',
  api_key: '',
  is_active: true,
  is_default: false,
  // 成本治理：每 1K tokens 输入/输出单价与月度预算（美元），字符串输入，留空表示未设置。
  input_price_per_1k: '',
  output_price_per_1k: '',
  monthly_budget_usd: '',
});

// 将价格输入框的字符串转换为 number | null；空串或非法值一律为 null。
function toPrice(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === '') {
    return null;
  }
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

const requiresKey = computed(() => !formState.id); // 新增时不建议 key 为空，编辑时可以不改 key
const canSave = computed(() => {
  const providerValid = formState.provider_name.trim().length > 0;
  const modelValid = formState.model_name.trim().length > 0;
  const keyValid = formState.api_key.trim().length > 0;
  return providerValid && modelValid && (!requiresKey.value || keyValid);
});

// 编辑配置
function startEdit(cfg: LLMConfigSummary) {
  formState.id = cfg.id ?? null;
  formState.provider_name = cfg.provider_name ?? '';
  formState.display_name = cfg.display_name ?? '';
  formState.base_url = cfg.base_url ?? '';
  formState.model_name = cfg.model_name ?? '';
  formState.api_key = ''; // 不回显 key
  formState.is_active = cfg.is_active ?? true;
  formState.is_default = cfg.is_default ?? false;
  formState.input_price_per_1k = cfg.input_price_per_1k != null ? String(cfg.input_price_per_1k) : '';
  formState.output_price_per_1k = cfg.output_price_per_1k != null ? String(cfg.output_price_per_1k) : '';
  formState.monthly_budget_usd = cfg.monthly_budget_usd != null ? String(cfg.monthly_budget_usd) : '';
}

function cancelEdit() {
  resetForm();
}

function resetForm() {
  formState.id = null;
  formState.provider_name = '';
  formState.display_name = '';
  formState.base_url = '';
  formState.model_name = '';
  formState.api_key = '';
  formState.is_active = true;
  formState.is_default = false;
  formState.input_price_per_1k = '';
  formState.output_price_per_1k = '';
  formState.monthly_budget_usd = '';
}

async function submitConfig() {
  if (!canSave.value) {
    return;
  }

  const trimmedKey = formState.api_key.trim();
  const payload = {
    id: formState.id,
    provider_name: formState.provider_name.trim(),
    display_name: formState.display_name.trim() || null,
    base_url: formState.base_url.trim() || null,
    model_name: formState.model_name.trim(),
    api_key: trimmedKey ? trimmedKey : undefined,
    is_active: formState.is_active,
    is_default: formState.is_default,
    input_price_per_1k: toPrice(formState.input_price_per_1k),
    output_price_per_1k: toPrice(formState.output_price_per_1k),
    monthly_budget_usd: toPrice(formState.monthly_budget_usd),
  };

  try {
    await llmStore.saveConfig(payload);
    toastStore.showSuccess('大模型配置保存成功');
    resetForm();
  } catch (err: any) {
    toastStore.showError(err.message || '保存失败');
  }
}

defineExpose({ startEdit });
</script>

<template>
  <SectionCard
    :title="formState.id ? '编辑配置' : '新增配置'"
    :subtitle="formState.id ? `正在修改 ${formState.display_name || '配置'}` : '接入更多模型并启用'"
  >
    <form class="grid gap-[14px] mt-2" @submit.prevent="submitConfig">
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>Provider 名称 *</span>
        <input
          v-model="formState.provider_name"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="provider_name"
          type="text"
          :disabled="llmStore.loading || llmStore.saving"
          placeholder="例如 openai_compatible"
          required
        />
      </label>
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>显示名称</span>
        <input
          v-model="formState.display_name"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="display_name"
          type="text"
          :disabled="llmStore.loading || llmStore.saving"
          placeholder="例如 DeepSeek-Chat"
        />
      </label>
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>Base URL</span>
        <input
          v-model="formState.base_url"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="base_url"
          type="text"
          :disabled="llmStore.loading || llmStore.saving"
          placeholder="例如 https://api.deepseek.com/v1"
        />
      </label>
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>Model 名称 *</span>
        <input
          v-model="formState.model_name"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="model_name"
          type="text"
          :disabled="llmStore.loading || llmStore.saving"
          placeholder="例如 deepseek-chat"
          required
        />
      </label>
      <div class="grid gap-[14px] sm:grid-cols-2">
        <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
          <span>输入单价（$/1K tokens）</span>
          <input
            v-model="formState.input_price_per_1k"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
            name="input_price_per_1k"
            type="number"
            step="0.0001"
            min="0"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 0.0002"
          />
        </label>
        <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
          <span>输出单价（$/1K tokens）</span>
          <input
            v-model="formState.output_price_per_1k"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
            name="output_price_per_1k"
            type="number"
            step="0.0001"
            min="0"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 0.002"
          />
        </label>
      </div>
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>月度预算（$）</span>
        <input
          v-model="formState.monthly_budget_usd"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="monthly_budget_usd"
          type="number"
          step="0.01"
          min="0"
          :disabled="llmStore.loading || llmStore.saving"
          placeholder="留空表示不限制"
        />
        <small class="text-text-faint">用于默认模型的“本月累计花费 vs 预算”超支告警</small>
      </label>
      <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
        <span>API Key {{ requiresKey ? '*' : '' }}</span>
        <input
          v-model="formState.api_key"
          data-surface="terminal-field"
          class="rounded-xl border border-border bg-field px-[14px] py-2 text-text text-sm"
          name="api_key"
          type="password"
          :disabled="llmStore.loading || llmStore.saving"
          :placeholder="requiresKey ? '必填 API Key' : '留空表示保留当前 key'"
        />
        <small class="text-text-faint">{{ requiresKey ? '新模型配置必须填写 API key' : '不改 key 时可留空' }}</small>
      </label>

      <div class="flex items-center gap-6 py-1">
        <label class="flex items-center gap-2 cursor-pointer text-xs font-semibold text-text-faint">
          <input
            v-model="formState.is_active"
            type="checkbox"
            class="rounded bg-field border-border text-system"
            :disabled="llmStore.loading || llmStore.saving"
          />
          <span>启用该模型</span>
        </label>
        <label class="flex items-center gap-2 cursor-pointer text-xs font-semibold text-text-faint">
          <input
            v-model="formState.is_default"
            type="checkbox"
            class="rounded bg-field border-border text-system"
            :disabled="llmStore.loading || llmStore.saving"
          />
          <span>设为默认模型</span>
        </label>
      </div>

      <div class="flex flex-wrap items-center gap-3 mt-1">
        <button
          class="rounded-full bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] px-5 py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          type="submit"
          :disabled="!canSave || llmStore.saving"
        >
          {{ llmStore.saving ? '正在保存…' : (formState.id ? '更新配置' : '保存配置') }}
        </button>
        <button
          v-if="formState.id"
          class="rounded-full bg-white/[0.08] hover:bg-white/[0.15] px-5 py-2.5 font-semibold text-text transition"
          type="button"
          @click="cancelEdit"
        >
          取消
        </button>
      </div>
      <p v-if="llmStore.saveSuccess" class="text-xs text-success mt-1">{{ llmStore.saveSuccess }}</p>
      <p v-else-if="llmStore.saveError" class="text-xs text-danger mt-1">{{ llmStore.saveError }}</p>
      <p v-if="llmStore.testSuccess" class="text-xs text-success mt-1">{{ llmStore.testSuccess }}</p>
      <p v-else-if="llmStore.testError" class="text-xs text-danger mt-1">{{ llmStore.testError }}</p>
    </form>
  </SectionCard>
</template>
