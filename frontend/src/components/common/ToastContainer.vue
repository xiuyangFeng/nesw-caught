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
        class="pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-xl border p-4 shadow-2xl backdrop-blur-md transition-all duration-300 hover:scale-[1.02]"
        :class="{
          'border-emerald-500/30 bg-emerald-950/20 text-emerald-100 shadow-emerald-900/10': toast.type === 'success',
          'border-rose-500/30 bg-rose-950/20 text-rose-100 shadow-rose-900/10': toast.type === 'error',
          'border-amber-500/30 bg-amber-950/20 text-amber-100 shadow-amber-900/10': toast.type === 'warning',
          'border-blue-500/30 bg-blue-950/20 text-blue-100 shadow-blue-900/10': toast.type === 'info',
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
        <div class="flex-1 text-xs font-semibold leading-relaxed">
          {{ toast.message }}
        </div>

        <!-- Close Button -->
        <button
          class="ml-2 shrink-0 rounded-lg p-0.5 text-text-faint hover:bg-white/5 hover:text-text transition-colors active:scale-95"
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
            'bg-emerald-500 shadow-[0_0_12px_#10b981]': toast.type === 'success',
            'bg-rose-500 shadow-[0_0_12px_#ef4444]': toast.type === 'error',
            'bg-amber-500 shadow-[0_0_12px_#f59e0b]': toast.type === 'warning',
            'bg-blue-500 shadow-[0_0_12px_#3b82f6]': toast.type === 'info',
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
