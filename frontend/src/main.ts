import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import { recoverFromChunkError } from './utils/lazyImport';

// 字体自托管（替代原 Google Fonts CDN），仅拉丁 Inter + 等宽 JetBrains Mono，
// 中文回落系统字体。见 docs/superpowers/specs/2026-07-18-cyber-terminal-restyle-design.md §5
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import '@fontsource/jetbrains-mono/600.css';
import '@fontsource/jetbrains-mono/700.css';
import './assets/main.css';

const app = createApp(App);

// Log otherwise-unhandled component errors instead of letting them silently
// break reactivity. The <RouteErrorBoundary> around <RouterView> contains view
// errors; this is the last-resort net for anything outside that subtree.
app.config.errorHandler = (err, _instance, info) => {
  // eslint-disable-next-line no-console
  console.error('[vue] unhandled error:', info, err);
};

// Vite emits this when a preloaded route chunk fails to load (stale build after
// a redeploy, dev-server 504). Recover with a guarded reload so navigation
// between modules never dead-ends into a page the user must refresh by hand.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  recoverFromChunkError();
});

app.use(createPinia());
app.use(router);
app.mount('#app');
