<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { useLlmStore } from '../stores/llmStore';
import { useToastStore } from '../stores/toastStore';
import { formatMarketTime } from '../utils/time';
import { apiClient } from '../api/client';

const llmStore = useLlmStore();
const toastStore = useToastStore();

interface TokenStats {
  overall: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  models: {
    model_name: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    call_count: number;
  }[];
  operations: {
    operation_type: string;
    total_tokens: number;
  }[];
  daily: {
    date: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  }[];
}

const stats = ref<TokenStats | null>(null);
const loadingStats = ref(false);

async function loadStats() {
  loadingStats.value = true;
  try {
    const res = await apiClient.getLlmStats();
    stats.value = res.data;
  } catch (err) {
    console.error('Failed to load stats', err);
  } finally {
    loadingStats.value = false;
  }
}

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
    toastStore.showSuccess('大模型配置保存成功');
    resetForm();
  } catch (err: any) {
    toastStore.showError(err.message || '保存失败');
  }
}

async function submitConnectionTest() {
  if (!hasActiveConfig.value) {
    return;
  }
  try {
    await llmStore.testConnection();
    toastStore.showSuccess(llmStore.testSuccess || '连接测试成功！');
  } catch (err: any) {
    toastStore.showError(err.message || '连接测试失败');
  }
}

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

const hoveredIdx = ref<number | null>(null);
const dailyData = computed(() => stats.value?.daily || []);

const chartWidth = 500;
const chartHeight = 140;
const paddingLeft = 40;
const paddingRight = 20;
const paddingTop = 15;
const paddingBottom = 20;

function handleChartMouseMove(e: MouseEvent) {
  if (!dailyData.value.length) return;
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const relativeX = clickX / rect.width;
  const idx = Math.round(relativeX * (dailyData.value.length - 1));
  if (idx >= 0 && idx < dailyData.value.length) {
    hoveredIdx.value = idx;
  }
}

function handleChartMouseLeave() {
  hoveredIdx.value = null;
}

const chartPoints = computed(() => {
  const data = dailyData.value;
  if (!data.length) return [];
  const maxVal = Math.max(...data.map(d => d.total_tokens), 0) || 1000;
  const W = chartWidth - paddingLeft - paddingRight;
  const H = chartHeight - paddingTop - paddingBottom;
  
  return data.map((d, i) => {
    const x = paddingLeft + (data.length > 1 ? (i / (data.length - 1)) * W : W / 2);
    const y = chartHeight - paddingBottom - (d.total_tokens / maxVal) * H;
    return { x, y, ...d };
  });
});

const linePath = computed(() => {
  const pts = chartPoints.value;
  if (!pts.length) return '';
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
});

const areaPath = computed(() => {
  const pts = chartPoints.value;
  if (!pts.length) return '';
  const start = linePath.value;
  const lastX = pts[pts.length - 1].x;
  const firstX = pts[0].x;
  const yBottom = chartHeight - paddingBottom;
  return `${start} L ${lastX.toFixed(1)} ${yBottom} L ${firstX.toFixed(1)} ${yBottom} Z`;
});

onMounted(() => {
  void llmStore.loadConfig();
  void llmStore.loadAllConfigs();
  void loadStats();
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

    <!-- Model usage token auditing dashboard -->
    <SectionCard v-if="stats" title="模型额度审计控制台 (LLM Token Usage Console)" subtitle="系统运行过程中产生的 Token 消耗审计与成本估算">
      <template #action>
        <button
          class="rounded-lg bg-white/[0.05] hover:bg-white/[0.1] px-2.5 py-1 text-xs text-text-faint hover:text-text transition-colors"
          type="button"
          :disabled="loadingStats"
          @click="loadStats"
        >
          {{ loadingStats ? '刷新中...' : '🔄 刷新审计' }}
        </button>
      </template>

      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mt-2">
        <!-- Metric 1: Total Tokens -->
        <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
          <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Total Tokens</div>
          <div class="text-xl font-bold text-text-faint font-mono mt-1 group-hover:text-text transition-colors">
            {{ stats.overall.total_tokens.toLocaleString() }}
          </div>
          <div class="text-[10px] text-text-faint mt-1 flex justify-between">
            <span>In: {{ stats.overall.prompt_tokens.toLocaleString() }}</span>
            <span>Out: {{ stats.overall.completion_tokens.toLocaleString() }}</span>
          </div>
          <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-500/80 shadow-[0_0_8px_#3b82f6]" />
        </div>

        <!-- Metric 2: Estimated Cost -->
        <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
          <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Estimated Cost</div>
          <div class="text-xl font-bold text-emerald-400 font-mono mt-1">
            ${{ (stats.overall.total_tokens * 0.0000002).toFixed(6) }}
          </div>
          <div class="text-[10px] text-text-faint mt-1">
            基于 $0.20/M tokens 均价估算
          </div>
          <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-emerald-500/80 shadow-[0_0_8px_#10b981]" />
        </div>

        <!-- Metric 3: Active Models Stats -->
        <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
          <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Active Providers</div>
          <div class="text-xl font-bold text-purple-400 font-mono mt-1">
            {{ stats.models.length }} <span class="text-xs text-text-faint">Models</span>
          </div>
          <div class="text-[10px] text-text-faint mt-1 truncate">
            已触发 {{ stats.models.reduce((acc, m) => acc + m.call_count, 0) }} 次接口请求
          </div>
          <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-purple-500/80 shadow-[0_0_8px_#a855f7]" />
        </div>

        <!-- Metric 4: Top Model -->
        <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
          <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Top Pick Model</div>
          <div class="text-xs font-bold text-text truncate mt-1.5">
            {{ stats.models[0]?.model_name || 'N/A' }}
          </div>
          <div class="text-[10px] text-text-faint mt-1">
            占比: {{ stats.overall.total_tokens ? Math.round((stats.models[0]?.total_tokens || 0) / stats.overall.total_tokens * 100) : 0 }}%
          </div>
          <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-amber-500/80 shadow-[0_0_8px_#f59e0b]" />
        </div>
      </div>

      <!-- Token Trend Chart Section -->
      <div class="mt-5 relative border border-border/50 bg-white/[0.01] rounded-2xl p-4 overflow-hidden" data-role="token-trend-card">
        <div class="flex items-center justify-between mb-3">
          <div class="text-xs font-bold text-text-faint tracking-wider uppercase font-mono">7日 Token 消耗趋势</div>
          <div class="text-[10px] text-muted font-mono">鼠标悬停可显示明细</div>
        </div>

        <div v-if="dailyData.length > 0" class="relative w-full h-[140px]" data-role="chart-container">
          <svg
            class="w-full h-full cursor-crosshair overflow-visible"
            viewBox="0 0 500 140"
            preserveAspectRatio="none"
            @mousemove="handleChartMouseMove"
            @mouseleave="handleChartMouseLeave"
          >
            <defs>
              <linearGradient id="chartAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.25" />
                <stop offset="100%" stop-color="#22d3ee" stop-opacity="0.0" />
              </linearGradient>
            </defs>

            <!-- Horizontal grid lines -->
            <g stroke="rgba(255,255,255,0.04)" stroke-dasharray="2 3">
              <line x1="40" y1="15" x2="480" y2="15" />
              <line x1="40" y1="50" x2="480" y2="50" />
              <line x1="40" y1="85" x2="480" y2="85" />
              <line x1="40" y1="120" x2="480" y2="120" />
            </g>

            <!-- X Axis Labels -->
            <g fill="rgba(255,255,255,0.4)" font-size="8" font-family="monospace" text-anchor="middle">
              <text v-for="(p, i) in chartPoints" :key="i" :x="p.x" y="134">
                {{ p.date.substring(5) }}
              </text>
            </g>

            <!-- Y Axis indicators (Max / Min) -->
            <g fill="rgba(255,255,255,0.25)" font-size="7" font-family="monospace" text-anchor="end">
              <text x="32" y="18">{{ Math.max(...dailyData.map(d => d.total_tokens), 0).toLocaleString() }}</text>
              <text x="32" y="123">0</text>
            </g>

            <!-- Area block -->
            <path :d="areaPath" fill="url(#chartAreaGrad)" />

            <!-- Highlight line -->
            <path :d="linePath" fill="none" stroke="#22d3ee" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />

            <!-- Cursor crosshair vertical line -->
            <line
              v-if="hoveredIdx !== null && chartPoints[hoveredIdx]"
              :x1="chartPoints[hoveredIdx].x"
              y1="15"
              :x2="chartPoints[hoveredIdx].x"
              y2="120"
              stroke="#22d3ee"
              stroke-opacity="0.3"
              stroke-dasharray="2 2"
            />

            <!-- Dots -->
            <circle
              v-for="(p, i) in chartPoints"
              :key="i"
              :cx="p.x"
              :cy="p.y"
              r="3.5"
              fill="#0f172a"
              :stroke="hoveredIdx === i ? '#ffffff' : '#22d3ee'"
              stroke-width="1.5"
              :style="{ transform: hoveredIdx === i ? 'scale(1.5)' : 'none' }"
              class="transition-all duration-100 origin-center"
            />
          </svg>

          <!-- Interactive HTML tooltip popover -->
          <div
            v-if="hoveredIdx !== null && chartPoints[hoveredIdx]"
            class="absolute pointer-events-none rounded-xl border border-cyan-500/30 bg-black/90 p-2.5 text-[10px] text-text-faint font-mono shadow-lg shadow-cyan-950/20 backdrop-blur-md z-10 space-y-1 w-28"
            :style="{
              left: `${(chartPoints[hoveredIdx].x / chartWidth) * 100}%`,
              top: `${(chartPoints[hoveredIdx].y / chartHeight) * 100 - 50}%`,
              transform: 'translate(-50%, -100%)'
            }"
          >
            <div class="text-text font-bold border-b border-white/10 pb-0.5 mb-1">{{ chartPoints[hoveredIdx].date }}</div>
            <div class="flex justify-between gap-1">
              <span>Total:</span>
              <span class="text-cyan-400 font-bold">{{ chartPoints[hoveredIdx].total_tokens.toLocaleString() }}</span>
            </div>
            <div class="flex justify-between gap-1 text-[9px] text-muted">
              <span>Prompt:</span>
              <span>{{ chartPoints[hoveredIdx].prompt_tokens.toLocaleString() }}</span>
            </div>
            <div class="flex justify-between gap-1 text-[9px] text-muted">
              <span>Reply:</span>
              <span>{{ chartPoints[hoveredIdx].completion_tokens.toLocaleString() }}</span>
            </div>
          </div>
        </div>

        <div v-else class="flex flex-col items-center justify-center py-8 text-center border border-dashed border-border/40 rounded-xl bg-white/[0.005]">
          <span class="text-xl mb-1">📊</span>
          <p class="text-xs text-text-faint">暂无足够历史 Token 用量趋势数据</p>
        </div>
      </div>

      <!-- Detail rows showing model stats -->
      <div v-if="stats.models.length > 0" class="mt-4 border border-border/40 bg-black/10 rounded-xl p-3 overflow-hidden text-xs">
        <div class="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted font-mono border-b border-border/30 pb-2 mb-2">
          <span>Model Name</span>
          <div class="flex gap-8">
            <span class="w-16 text-right">Calls</span>
            <span class="w-20 text-right">Total Tokens</span>
          </div>
        </div>
        <div class="space-y-2">
          <div v-for="m in stats.models" :key="m.model_name" class="flex items-center justify-between font-mono text-text-faint">
            <span class="truncate pr-4">{{ m.model_name }}</span>
            <div class="flex gap-8 shrink-0">
              <span class="w-16 text-right">{{ m.call_count }}</span>
              <span class="w-20 text-right text-text">{{ m.total_tokens.toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
    </SectionCard>

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
