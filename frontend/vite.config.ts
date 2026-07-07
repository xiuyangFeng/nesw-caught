import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import fs from 'fs';
import path from 'path';

// 读取本地 App Token 以便注入前端
let appToken = '';
try {
  const tokenPath = path.resolve(__dirname, '../data/.app_token');
  if (fs.existsSync(tokenPath)) {
    appToken = fs.readFileSync(tokenPath, 'utf-8');
  }
} catch (e) {
  // 忽略读取错误，如果是首次初始化可能会在后端生成前读取，会在重试或下一次启动时正常
}

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_TOKEN__: JSON.stringify(appToken.trim()),
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
