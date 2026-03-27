<script setup lang="ts">
import { computed } from 'vue';

import type { KlineIndicatorTemplate, KlineSubIndicator } from '../../types/api';

const props = defineProps<{
  templates: KlineIndicatorTemplate[];
  activeTemplateId: string;
  subIndicator: KlineSubIndicator;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  templateApply: [templateId: string];
  templateSave: [];
  templateDelete: [templateId: string];
  subindicatorChange: [indicator: KlineSubIndicator];
}>();

const activeTemplate = computed(() => props.templates.find((template) => template.id === props.activeTemplateId) ?? null);

function summary(template: KlineIndicatorTemplate | null) {
  if (!template) {
    return '--';
  }
  return template.overlayIndicators
    .map((indicator) => {
      if (indicator.kind === 'BOLL') {
        return `BOLL(${indicator.params.period},${indicator.params.stdDev})`;
      }
      return `${indicator.kind}${indicator.params.periods.join('/')}`;
    })
    .join(' · ');
}
</script>

<template>
  <aside class="grid gap-3 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(180deg,rgba(15,22,34,0.98),rgba(9,14,22,0.98))] p-3" data-role="kline-indicator-workbench">
    <div class="grid gap-1">
      <div class="flex items-center justify-between gap-2">
        <span class="text-[10px] uppercase tracking-[0.18em] text-[#ffb77d]">指标工作台</span>
        <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">{{ subIndicator }}</span>
      </div>
      <strong class="text-sm text-text" data-role="active-template-name">{{ activeTemplate?.name ?? '经典均线' }}</strong>
      <p class="m-0 text-[11px] leading-5 text-text-faint" data-role="active-template-summary">
        {{ summary(activeTemplate) }}
      </p>
    </div>

    <div class="grid gap-2" data-role="template-library">
      <button
        v-for="template in templates"
        :key="template.id"
        type="button"
        class="rounded-[14px] border px-3 py-2 text-left"
        :class="template.id === activeTemplateId ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)]' : 'border-border/70 bg-[rgba(255,255,255,0.02)]'"
        :data-role="`template-card-${template.id}`"
        :disabled="disabled"
        @click="emit('templateApply', template.id)"
      >
        <div class="flex items-center justify-between gap-2">
          <strong class="text-sm text-text">{{ template.name }}</strong>
          <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ template.source }}</span>
        </div>
      </button>
    </div>

    <div class="flex flex-wrap gap-2">
      <button type="button" data-role="template-save" class="rounded-full border border-border/70 px-3 py-1 text-[11px] text-text-faint" @click="emit('templateSave')">
        另存为模板
      </button>
      <button
        type="button"
        data-role="template-reset"
        class="rounded-full border border-border/70 px-3 py-1 text-[11px] text-text-faint"
        :disabled="disabled"
        @click="emit('templateApply', 'preset-classic')"
      >
        重置为默认
      </button>
      <button
        type="button"
        data-role="template-delete"
        class="rounded-full border border-[rgba(255,111,134,0.28)] px-3 py-1 text-[11px] text-[#ff9dad]"
        :disabled="!activeTemplate || activeTemplate.source === 'preset'"
        @click="activeTemplate && emit('templateDelete', activeTemplate.id)"
      >
        删除模板
      </button>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="item in ['VOL', 'MACD', 'KDJ', 'RSI']"
        :key="item"
        type="button"
        class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
        :class="subIndicator === item ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
        :data-role="`subindicator-${item}`"
        @click="emit('subindicatorChange', item as KlineSubIndicator)"
      >
        {{ item }}
      </button>
    </div>
  </aside>
</template>
