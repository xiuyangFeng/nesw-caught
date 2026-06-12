<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { useLlmStore } from '../stores/llmStore';
import { formatMarketTime } from '../utils/time';

const llmStore = useLlmStore();

const formState = reactive({
  id: null as number | null,
  provider_name: '',
  display_name: '',
  base_url: '',
  model_name: '',
  api_key: '',
  is_active: true,
  is_default: false,
});

const hasConfigs = computed(() => llmStore.configs.length > 0);
const hasActiveConfig = computed(() => llmStore.config?.configured === true);
const requiresKey = computed(() => !formState.id); // 新增时不建议 key 为空，编辑时可以不改 key
const canSave = computed(() => {
  const providerValid = formState.provider_name.trim().length > 0;
  const modelValid = formState.model_name.trim().length > 0;
  const keyValid = formState.api_key.trim().length > 0;
  return providerValid && modelValid && (!requiresKey.value || keyValid);
});

const lastUpdatedLabel = computed(() => {
  if (!llmStore.config?.updated_at) {
    return null;
  }
  return formatMarketTime(llmStore.config.updated_at, 'hk');
});

// 编辑配置
function startEdit(cfg: any) {
  formState.id = cfg.id;
  formState.provider_name = cfg.provider_name ?? '';
  formState.display_name = cfg.display_name ?? '';
  formState.base_url = cfg.base_url ?? '';
  formState.model_name = cfg.model_name ?? '';
  formState.api_key = ''; // 不回显 key
  formState.is_active = cfg.is_active ?? true;
  formState.is_default = cfg.is_default ?? false;
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
  };

  try {
    await llmStore.saveConfig(payload);
    resetForm();
  } catch {
    // 错误由 store 浮现
  }
}

async function submitConnectionTest() {
  if (!hasActiveConfig.value) {
    return;
  }
  try {
    await llmStore.testConnection();
  } catch {
    // 错误由 store 浮现
  }
}

async function handleDelete(id: number) {
  if (confirm('确定要删除这个模型配置吗？')) {
    await llmStore.deleteConfig(id);
  }
}

async function handleSetDefault(id: number) {
  await llmStore.setDefaultConfig(id);
}

async function handleToggleActive(id: number, currentActive: boolean) {
  await llmStore.toggleConfigActive(id, !currentActive);
}

onMounted(() => {
  void llmStore.loadConfig();
  void llmStore.loadAllConfigs();
});
</script>

<template>
  <div class="grid gap-6">
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="page-title text-2xl font-bold tracking-tight">LLM Settings</h1>
        <p class="page-subtitle text-muted text-sm mt-1">配置和管理系统中多套大语言模型驱动，可快速切换或分配给聊天和翻译任务。</p>
      </div>
      <div v-if="hasActiveConfig" class="flex items-center gap-3">
        <button
          class="rounded-full bg-[linear-gradient(135deg,#0f766e,#14b8a6)] px-5 py-2 font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
          type="button"
          data-testid="test-connection-button"
          :disabled="llmStore.loading || llmStore.saving || llmStore.testingConnection"
          @click="submitConnectionTest"
        >
          {{ llmStore.testingConnection ? '正在测试默认模型连接…' : '测试默认连接' }}
        </button>
      </div>
    </header>

    <div class="grid gap-6 lg:grid-cols-[1fr_380px]" data-role="llm-settings-grid">
      <!-- 左侧：模型列表 -->
      <div class="grid gap-4 self-start">
        <SectionCard title="已配置模型列表" subtitle="系统支持的全部 LLM 配置，可在提问聊天时任意选择">
          <p v-if="llmStore.loadError" class="text-danger my-2">{{ llmStore.loadError }}</p>
          <div v-if="!hasConfigs" class="text-center py-8 text-text-faint">
            <p>尚未配置任何模型，请在右侧添加您的首个 LLM 配置。</p>
          </div>
          <div v-else class="grid gap-3.5 mt-2">
            <div
              v-for="cfg in llmStore.configs"
              :key="cfg.id ?? 0"
              class="relative flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-[20px] border border-border/80 bg-white/[0.02] p-4.5 transition duration-150 hover:border-border hover:bg-white/[0.03]"
              :class="cfg.is_default ? 'border-[#ff9f2f3a] bg-[#ff9f2f04]' : ''"
            >
              <div class="flex items-start gap-3.5">
                <!-- 状态呼吸灯 -->
                <div class="mt-1.5 flex items-center justify-center">
                  <span
                    class="ping-dot inline-block h-2.5 w-2.5 rounded-full"
                    :class="cfg.is_active ? 'bg-success' : 'bg-muted'"
                    :title="cfg.is_active ? '已启用' : '已禁用'"
                  />
                </div>
                <!-- 详情 -->
                <div class="grid gap-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="font-bold text-text text-[15px]">
                      {{ cfg.display_name || cfg.provider_name }}
                    </span>
                    <span
                      v-if="cfg.is_default"
                      class="rounded-full bg-[linear-gradient(135deg,#ff9f2f,#ff7e00)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm"
                    >
                      默认
                    </span>
                  </div>
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-faint">
                    <span>Provider: <code class="bg-white/[0.04] px-1 rounded">{{ cfg.provider_name }}</code></span>
                    <span>Model: <code class="bg-white/[0.04] px-1 rounded">{{ cfg.model_name }}</code></span>
                  </div>
                  <div v-if="cfg.base_url" class="text-[11px] text-muted font-mono truncate max-w-md mt-0.5">
                    {{ cfg.base_url }}
                  </div>
                </div>
              </div>

              <!-- 操作区 -->
              <div class="flex flex-wrap items-center gap-2.5 md:self-center">
                <button
                  class="rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white/[0.05] hover:bg-white/[0.1] text-text transition"
                  type="button"
                  @click="startEdit(cfg)"
                >
                  编辑
                </button>
                <button
                  class="rounded-lg px-2.5 py-1.5 text-xs font-semibold transition"
                  type="button"
                  :class="cfg.is_active ? 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-400' : 'bg-success/10 hover:bg-success/20 text-success'"
                  @click="handleToggleActive(cfg.id!, cfg.is_active ?? false)"
                >
                  {{ cfg.is_active ? '禁用' : '启用' }}
                </button>
                <button
                  v-if="cfg.is_active && !cfg.is_default"
                  class="rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition"
                  type="button"
                  @click="handleSetDefault(cfg.id!)"
                >
                  设为默认
                </button>
                <button
                  class="rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-danger/10 hover:bg-danger/20 text-danger transition"
                  type="button"
                  @click="handleDelete(cfg.id!)"
                >
                  删除
                </button>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <!-- 右侧：表单配置 -->
      <div class="grid gap-4 self-start">
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.ping-dot {
  position: relative;
  display: inline-flex;
}
.ping-dot::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: inherit;
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
  opacity: 0.65;
}
@keyframes ping {
  75%, 100% {
    transform: scale(2.8);
    opacity: 0;
  }
}
</style>
