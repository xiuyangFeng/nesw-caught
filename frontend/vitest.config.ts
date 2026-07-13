import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
    // 为「原生 Web Storage 会抛错」的环境（Node 22+ 实验性全局 storage）提供内存兜底，
    // 让真实挂载 Pinia 应用的导航冒烟测试可离线运行；storage 正常时为 no-op。
    setupFiles: ['./vitest.setup.ts'],
    environmentOptions: {
      jsdom: {
        url: 'http://localhost/',
      },
    },
  },
});
