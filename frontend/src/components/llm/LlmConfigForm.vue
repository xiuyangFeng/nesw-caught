<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { useLlmStore } from '../../stores/llmStore';
import { useToastStore } from '../../stores/toastStore';
import type { LLMConfigSummary } from '../../types/api';
import { LLM_PROVIDER_PRESETS } from './providerPresets';

const llmStore = useLlmStore();
const toastStore = useToastStore();
const emit = defineEmits<{
  saved: [];
  cancel: [];
}>();

type NumericInput = string | number | null | undefined;

interface LlmConfigFormState {
  id: number | null;
  provider_name: string;
  display_name: string;
  base_url: string;
  model_name: string;
  api_key: string;
  is_active: boolean;
  is_default: boolean;
  input_price_per_1k: NumericInput;
  output_price_per_1k: NumericInput;
  monthly_budget_usd: NumericInput;
}

const formState = reactive<LlmConfigFormState>({
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

const originalBaseUrl = ref('');
const selectedPresetId = ref<string | null>(null);
const activePreset = computed(() => (
  LLM_PROVIDER_PRESETS.find((preset) => preset.id === selectedPresetId.value) ?? null
));

function applyPreset(presetId: string) {
  const preset = LLM_PROVIDER_PRESETS.find((item) => item.id === presetId);
  if (!preset) return;

  selectedPresetId.value = preset.id;
  formState.provider_name = 'openai_compatible';
  formState.display_name = preset.name;
  formState.base_url = preset.baseUrl;
  formState.model_name = preset.defaultModel;
}

function useCustomConfig() {
  selectedPresetId.value = null;
}

function trimText(raw: string | null | undefined): string {
  return typeof raw === 'string' ? raw.trim() : '';
}

function parseOptionalNonNegativeNumber(raw: NumericInput, label: string): { value: number | null; error: string | null } {
  if (raw === null || raw === undefined || raw === '') {
    return { value: null, error: null };
  }

  const normalized = typeof raw === 'number' ? raw : raw.trim();
  if (normalized === '') {
    return { value: null, error: null };
  }

  const value = typeof normalized === 'number' ? normalized : Number(normalized);
  if (!Number.isFinite(value)) {
    return { value: null, error: `${label}必须是有效数字` };
  }
  if (value < 0) {
    return { value: null, error: `${label}不能小于 0` };
  }
  return { value, error: null };
}

function validateBaseUrl(raw: string): string | null {
  const value = trimText(raw);
  if (!value) {
    return null;
  }
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) {
      return 'Base URL 仅支持 http:// 或 https:// 地址';
    }
  } catch {
    return '请输入完整有效的 Base URL，例如 https://api.example.com/v1';
  }
  return null;
}

const baseUrlChanged = computed(() => (
  formState.id !== null && trimText(formState.base_url) !== originalBaseUrl.value
));
const requiresKey = computed(() => formState.id === null || baseUrlChanged.value);
const inputPrice = computed(() => parseOptionalNonNegativeNumber(formState.input_price_per_1k, '输入单价'));
const outputPrice = computed(() => parseOptionalNonNegativeNumber(formState.output_price_per_1k, '输出单价'));
const monthlyBudget = computed(() => parseOptionalNonNegativeNumber(formState.monthly_budget_usd, '月度预算'));
const validationErrors = computed(() => ({
  provider_name: trimText(formState.provider_name) ? null : '请输入 Provider 名称',
  base_url: validateBaseUrl(formState.base_url),
  model_name: trimText(formState.model_name) ? null : '请输入 Model 名称',
  api_key: requiresKey.value && !trimText(formState.api_key)
    ? (baseUrlChanged.value ? '修改 Base URL 后必须重新输入明文 API Key' : '新模型配置必须填写 API Key')
    : null,
  input_price_per_1k: inputPrice.value.error,
  output_price_per_1k: outputPrice.value.error,
  monthly_budget_usd: monthlyBudget.value.error,
}));
const canSave = computed(() => {
  return Object.values(validationErrors.value).every(error => error === null);
});
const saveDisabledReason = computed(() => Object.values(validationErrors.value).find(Boolean) ?? '');

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
  originalBaseUrl.value = trimText(cfg.base_url);
  selectedPresetId.value = LLM_PROVIDER_PRESETS.find((preset) => preset.baseUrl === originalBaseUrl.value)?.id ?? null;
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
  originalBaseUrl.value = '';
  selectedPresetId.value = null;
}

async function submitConfig() {
  if (!canSave.value) {
    return;
  }

  const trimmedKey = trimText(formState.api_key);
  const payload = {
    id: formState.id,
    provider_name: trimText(formState.provider_name),
    display_name: trimText(formState.display_name) || null,
    base_url: trimText(formState.base_url) || null,
    model_name: trimText(formState.model_name),
    api_key: trimmedKey ? trimmedKey : undefined,
    is_active: formState.is_active,
    is_default: formState.is_default,
    input_price_per_1k: inputPrice.value.value,
    output_price_per_1k: outputPrice.value.value,
    monthly_budget_usd: monthlyBudget.value.value,
  };

  try {
    await llmStore.saveConfig(payload);
    toastStore.showSuccess('大模型配置保存成功');
    resetForm();
    emit('saved');
  } catch (err: any) {
    toastStore.showError(err.message || '保存失败');
  }
}

defineExpose({ startEdit, resetForm });
</script>

<template>
  <form class="grid gap-4" data-role="llm-config-form" @submit.prevent="submitConfig">
      <section class="grid gap-3 rounded-xl border border-border bg-panel/50 p-3" aria-label="模型服务快捷预设">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-xs font-bold text-text">快捷接入</p>
            <p class="mt-1 text-[11px] leading-5 text-text-faint">选择服务后自动填写公开地址和推荐模型，API Key 不会被改动。</p>
          </div>
          <button
            class="shrink-0 rounded-full border border-border px-2.5 py-1 text-[11px] text-text-faint transition hover:border-accent hover:text-text"
            type="button"
            :class="selectedPresetId === null ? 'border-accent bg-[var(--accent-soft)] text-accent' : ''"
            @click="useCustomConfig"
          >
            自定义
          </button>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <button
            v-for="preset in LLM_PROVIDER_PRESETS"
            :key="preset.id"
            class="group rounded-lg border border-border bg-field px-3 py-2 text-left transition hover:-translate-y-0.5 hover:border-accent hover:bg-panel-strong"
            :class="selectedPresetId === preset.id ? 'border-accent bg-[var(--accent-soft)]' : ''"
            type="button"
            :data-testid="`provider-preset-${preset.id}`"
            :aria-pressed="selectedPresetId === preset.id"
            @click="applyPreset(preset.id)"
          >
            <span class="block text-xs font-bold text-text">{{ preset.shortName }}</span>
            <span class="mt-0.5 block truncate text-[10px] text-text-faint">{{ preset.defaultModel }}</span>
          </button>
        </div>
        <div v-if="activePreset" class="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-bg/40 px-3 py-2">
          <p class="min-w-0 text-[11px] leading-5 text-text-faint">{{ activePreset.description }}</p>
          <a
            class="shrink-0 text-[11px] font-semibold text-accent hover:underline"
            :href="activePreset.docsUrl"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="provider-docs-link"
          >
            官方文档 ↗
          </a>
        </div>
      </section>

      <div class="grid gap-3 md:grid-cols-2">
        <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
          <span>Provider 名称 *</span>
          <input
            v-model="formState.provider_name"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text text-sm"
            name="provider_name"
            type="text"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 openai_compatible"
            :aria-invalid="Boolean(validationErrors.provider_name)"
            required
          />
        </label>
        <label class="grid gap-1.5 font-semibold text-text-faint text-xs">
          <span>显示名称</span>
          <input
            v-model="formState.display_name"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text text-sm"
            name="display_name"
            type="text"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 DeepSeek-Chat"
          />
        </label>
      </div>

      <div class="grid gap-3 md:grid-cols-2">
        <label class="grid content-start gap-1.5 font-semibold text-text-faint text-xs">
          <span>Base URL</span>
          <input
            v-model="formState.base_url"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text text-sm"
            name="base_url"
            type="text"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 https://api.deepseek.com/v1"
            :aria-invalid="Boolean(validationErrors.base_url)"
          />
          <small v-if="validationErrors.base_url" class="text-danger">{{ validationErrors.base_url }}</small>
        </label>
        <label class="grid content-start gap-1.5 font-semibold text-text-faint text-xs">
          <span>Model 名称 *</span>
          <input
            v-model="formState.model_name"
            data-surface="terminal-field"
            class="rounded-xl border border-border bg-field px-[14px] py-2.5 text-text text-sm"
            name="model_name"
            type="text"
            :disabled="llmStore.loading || llmStore.saving"
            placeholder="例如 deepseek-chat"
            :aria-invalid="Boolean(validationErrors.model_name)"
            required
          />
          <div v-if="activePreset" class="flex flex-wrap gap-1.5 pt-1">
            <button
              v-for="model in activePreset.models"
              :key="model"
              class="rounded-full border border-border px-2 py-1 font-mono text-[10px] font-normal text-text-faint transition hover:border-accent hover:text-text"
              :class="formState.model_name === model ? 'border-accent bg-[var(--accent-soft)] text-accent' : ''"
              type="button"
              @click="formState.model_name = model"
            >
              {{ model }}
            </button>
          </div>
        </label>
      </div>

      <div class="grid gap-3 md:grid-cols-3">
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
            :aria-invalid="Boolean(validationErrors.input_price_per_1k)"
          />
          <small v-if="validationErrors.input_price_per_1k" class="text-danger">{{ validationErrors.input_price_per_1k }}</small>
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
            :aria-invalid="Boolean(validationErrors.output_price_per_1k)"
          />
          <small v-if="validationErrors.output_price_per_1k" class="text-danger">{{ validationErrors.output_price_per_1k }}</small>
        </label>
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
            :aria-invalid="Boolean(validationErrors.monthly_budget_usd)"
          />
          <small v-if="validationErrors.monthly_budget_usd" class="text-danger">{{ validationErrors.monthly_budget_usd }}</small>
        </label>
      </div>
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
          :aria-invalid="Boolean(validationErrors.api_key)"
        />
        <small v-if="validationErrors.api_key && baseUrlChanged" class="text-danger">{{ validationErrors.api_key }}</small>
        <small v-else class="text-text-faint">
          {{ formState.id === null ? '新模型配置必须填写 API Key' : (baseUrlChanged ? '修改服务地址后需要重新验证对应的 API Key' : '不改 Key 时可留空，系统会保留当前 Key') }}
        </small>
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

      <div class="flex flex-wrap items-center justify-end gap-3 border-t border-border/70 pt-4">
        <button
          class="rounded-full border border-border px-5 py-2.5 font-semibold text-text-faint transition hover:border-text-faint hover:text-text"
          type="button"
          data-role="cancel-llm-config"
          @click="emit('cancel')"
        >
          取消
        </button>
        <button
          class="rounded-full bg-[linear-gradient(135deg,var(--system),var(--accent))] px-5 py-2.5 font-semibold text-[var(--bg)] disabled:cursor-not-allowed disabled:opacity-50"
          type="submit"
          :disabled="!canSave || llmStore.saving"
          :title="!canSave ? saveDisabledReason : undefined"
        >
          {{ llmStore.saving ? '正在保存…' : (formState.id ? '更新配置' : '保存配置') }}
        </button>
      </div>
      <p v-if="llmStore.saveSuccess" class="text-xs text-success mt-1">{{ llmStore.saveSuccess }}</p>
      <p v-else-if="llmStore.saveError" class="text-xs text-danger mt-1">{{ llmStore.saveError }}</p>
      <p v-if="llmStore.testSuccess" class="text-xs text-success mt-1">{{ llmStore.testSuccess }}</p>
      <p v-else-if="llmStore.testError" class="text-xs text-danger mt-1">{{ llmStore.testError }}</p>
  </form>
</template>
