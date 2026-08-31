import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'

// 平台 HTTPS（自签证书）：Outlook Web Add-in 硬性要求 manifest 内所有 URL 为 https://
// （http 连 localhost 都不豁免）。检测到 server/certs/platform.{crt,key} 即启用 https，
// 缺失则维持 http 开发模式（生成命令见 docs/举报插件部署说明.md）。
const platformCert = fileURLToPath(new URL('../server/certs/platform.crt', import.meta.url))
const platformKey = fileURLToPath(new URL('../server/certs/platform.key', import.meta.url))
const httpsOpts = fs.existsSync(platformCert) && fs.existsSync(platformKey)
  ? { key: fs.readFileSync(platformKey), cert: fs.readFileSync(platformCert) }
  : undefined

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
    https: httpsOpts,
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
