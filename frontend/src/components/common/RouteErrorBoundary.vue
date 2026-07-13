<script setup lang="ts">
import { onErrorCaptured, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { isDynamicImportError, recoverFromChunkError } from '../../utils/lazyImport';

// Error boundary around <RouterView>. Without it, an uncaught error thrown while
// a route view sets up or renders propagates to the root and breaks the whole
// SPA's reactivity — the classic "switching modules freezes, must refresh"
// symptom. Here we contain the error so the shell/nav keep working, and clear
// it automatically when the user navigates to another module (no full refresh).

const route = useRoute();
const error = ref<Error | null>(null);

onErrorCaptured((err) => {
  // A chunk-load failure that slipped past the loader retry: recover by reload.
  if (isDynamicImportError(err)) {
    recoverFromChunkError();
    return false;
  }
  error.value = err instanceof Error ? err : new Error(String(err));
  // Surface it for debugging instead of swallowing silently.
  // eslint-disable-next-line no-console
  console.error('[RouteErrorBoundary] contained a view error:', err);
  return false; // stop propagation so the rest of the app stays alive
});

// Navigating away clears the error, so a broken module never blocks the others.
watch(
  () => route.fullPath,
  () => {
    error.value = null;
  },
);

function retry() {
  error.value = null;
}

function hardReload() {
  window.location.reload();
}
</script>

<template>
  <div
    v-if="error"
    class="route-error"
    role="alert"
    data-role="route-error-boundary"
  >
    <div class="route-error__panel">
      <p class="route-error__title">此模块加载时出错</p>
      <p class="route-error__detail">{{ error.message }}</p>
      <div class="route-error__actions">
        <button type="button" data-role="route-error-retry" @click="retry">重试</button>
        <button type="button" data-role="route-error-reload" @click="hardReload">刷新页面</button>
      </div>
      <p class="route-error__hint">可直接切换到其它模块，无需刷新整页。</p>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
.route-error {
  display: grid;
  place-items: center;
  min-height: 40vh;
  padding: 24px;
}

.route-error__panel {
  display: grid;
  gap: 10px;
  max-width: 520px;
  padding: 22px 24px;
  border: 1px solid rgba(255, 111, 134, 0.32);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(30, 16, 20, 0.9), rgba(18, 12, 16, 0.9));
  box-shadow: 0 0 24px rgba(255, 111, 134, 0.14);
}

.route-error__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #ff9fb0;
}

.route-error__detail {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #d6b9bf;
  word-break: break-word;
}

.route-error__actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.route-error__actions button {
  cursor: pointer;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
  padding: 7px 16px;
  font-size: 13px;
  color: #f2e7ea;
  transition: background 0.15s ease;
}

.route-error__actions button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.route-error__hint {
  margin: 2px 0 0;
  font-size: 11px;
  letter-spacing: 0.04em;
  color: #8ea0b5;
}
</style>
