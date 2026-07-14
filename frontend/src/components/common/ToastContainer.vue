<script setup lang="ts">
import { useToastStore } from '../../stores/toastStore';

const toastStore = useToastStore();
</script>

<template>
  <div class="fixed top-5 right-5 z-[9999] flex flex-col gap-3 w-full max-w-sm pointer-events-none">
    <TransitionGroup
      name="toast"
      tag="div"
      class="flex flex-col gap-3 w-full"
    >
      <div
        v-for="toast in toastStore.toasts"
        :key="toast.id"
        class="pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-md border bg-panel-strong p-3.5 shadow-shell transition-all duration-200"
        :class="{
          'border-[color-mix(in_srgb,var(--success)_30%,transparent)]': toast.type === 'success',
          'border-[color-mix(in_srgb,var(--danger)_30%,transparent)]': toast.type === 'error',
          'border-[color-mix(in_srgb,var(--warning)_30%,transparent)]': toast.type === 'warning',
          'border-[color-mix(in_srgb,var(--accent)_30%,transparent)]': toast.type === 'info',
        }"
        role="alert"
      >
        <!-- Icon Indicator -->
        <span class="mt-0.5 shrink-0 text-base leading-none">
          <span v-if="toast.type === 'success'">🟢</span>
          <span v-else-if="toast.type === 'error'">🔴</span>
          <span v-else-if="toast.type === 'warning'">🟡</span>
          <span v-else>🔵</span>
        </span>

        <!-- Message Content -->
        <div class="flex-1 text-xs font-semibold leading-relaxed text-text">
          {{ toast.message }}
        </div>

        <!-- Close Button -->
        <button
          class="ml-2 shrink-0 rounded-sm p-0.5 text-text-faint hover:bg-[var(--interactive-hover)] hover:text-text transition-colors active:scale-95"
          type="button"
          @click="toastStore.remove(toast.id)"
        >
          <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <!-- Ambient Side Highlight Line -->
        <div
          class="absolute left-0 top-0 bottom-0 w-1"
          :class="{
            'bg-[var(--success)]': toast.type === 'success',
            'bg-[var(--danger)]': toast.type === 'error',
            'bg-[var(--warning)]': toast.type === 'warning',
            'bg-[var(--accent)]': toast.type === 'info',
          }"
        />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-from {
  opacity: 0;
  transform: translateX(100px) scale(0.9);
}
.toast-enter-to {
  opacity: 1;
  transform: translateX(0) scale(1);
}
.toast-leave-from {
  opacity: 1;
  transform: scale(1);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(50px) scale(0.85);
}
</style>
