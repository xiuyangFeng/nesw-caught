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
    class="surface rounded-lg"
    :class="compact ? 'px-4 py-3.5' : 'p-4'"
    :data-compact="compact ? 'true' : 'false'"
  >
    <header class="mb-3.5 flex items-start justify-between gap-3 border-b border-border pb-3">
      <div>
        <p v-if="eyebrow" class="label-mono mb-1.5" data-role="section-eyebrow">
          {{ eyebrow }}
        </p>
        <h2 class="m-0 text-lg font-semibold leading-[1.3] tracking-[-0.02em] text-text">{{ title }}</h2>
        <p v-if="subtitle" class="mt-1.5 text-[13px] text-muted">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div>
      <slot />
    </div>
  </section>
</template>
