<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
  compact?: boolean;
  eyebrow?: string;
}>();
</script>

<template>
  <section
    class="surface terminal-surface rounded-[18px]"
    :class="compact ? 'px-[18px] py-4' : 'p-5'"
    :data-compact="compact ? 'true' : 'false'"
  >
    <header class="mb-4 flex items-start justify-between gap-3 border-b border-border pb-3">
      <div>
        <p v-if="eyebrow" class="mb-1.5 text-[11px] uppercase tracking-[0.18em] text-system" data-role="section-eyebrow">
          {{ eyebrow }}
        </p>
        <h2 class="m-0 text-lg leading-[1.3] tracking-[-0.02em] text-text">{{ title }}</h2>
        <p v-if="subtitle" class="mt-1.5 text-[13px] text-muted">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div>
      <slot />
    </div>
  </section>
</template>
