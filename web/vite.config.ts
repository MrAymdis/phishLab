import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0', // 局域网/容器可访问
    port: 5173,
    proxy: {
      // 管理端 API 与 SSE（dev 代理到后端 8080）
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // 举报插件端点
      '/report': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // 平台静态资源（上传的 Logo 等，后端 /static 挂载）
      '/static': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
