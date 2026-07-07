<script setup lang="ts">
import { computed } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { useLlmStore } from '../../stores/llmStore';
import { useToastStore } from '../../stores/toastStore';
import type { LLMConfigSummary } from '../../types/api';

const emit = defineEmits<{
  (e: 'edit', cfg: LLMConfigSummary): void;
}>();

const llmStore = useLlmStore();
const toastStore = useToastStore();

const hasConfigs = computed(() => llmStore.configs.length > 0);

async function handleDelete(id: number) {
  if (confirm('确定要删除这个模型配置吗？')) {
    try {
      await llmStore.deleteConfig(id);
      toastStore.showInfo('配置已删除');
    } catch (err: any) {
      toastStore.showError(err.message || '删除失败');
    }
  }
}

async function handleSetDefault(id: number) {
  try {
    await llmStore.setDefaultConfig(id);
    toastStore.showSuccess('默认模型已切换');
  } catch (err: any) {
    toastStore.showError(err.message || '设置默认失败');
  }
}

async function handleToggleActive(id: number, currentActive: boolean) {
  try {
    await llmStore.toggleConfigActive(id, !currentActive);
    toastStore.showInfo(!currentActive ? '模型已启用' : '模型已禁用');
  } catch (err: any) {
    toastStore.showError(err.message || '操作失败');
  }
}
</script>

<template>
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
              <span
                v-if="llmStore.pingStatuses[cfg.id!]?.loading"
                class="text-[10px] text-muted font-mono animate-pulse"
              >
                检测中…
              </span>
              <span
                v-else-if="llmStore.pingStatuses[cfg.id!]?.latency !== null"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold font-mono tracking-wider shadow-sm text-success bg-success/10 border border-success/30 shadow-[0_0_8px_rgba(126,216,158,0.15)]"
              >
                {{ llmStore.pingStatuses[cfg.id!].latency }} ms
              </span>
              <span
                v-else-if="llmStore.pingStatuses[cfg.id!]?.error !== null"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wider text-danger bg-danger/10 border border-danger/30 shadow-[0_0_8px_rgba(239,123,123,0.15)] cursor-help"
                :title="llmStore.pingStatuses[cfg.id!].error!"
              >
                连接失败
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
            :disabled="llmStore.pingStatuses[cfg.id!]?.loading"
            @click="llmStore.pingConfig(cfg.id!)"
          >
            {{ llmStore.pingStatuses[cfg.id!]?.loading ? '测速中…' : '📡 测速' }}
          </button>
          <button
            class="rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white/[0.05] hover:bg-white/[0.1] text-text transition"
            type="button"
            @click="emit('edit', cfg)"
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
