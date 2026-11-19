import fs from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // 本地 HTTPS 开关：start-dev.sh 会以环境变量传入；也允许直接在 shell 里设。
  // 打开后浏览器访问 https://localhost:5173，代理也走 HTTPS 到后端。
  const useHttps =
    env.OPSPILOT_HTTPS === '1' || process.env.OPSPILOT_HTTPS === '1'

  const certDir = fileURLToPath(new URL('../deploy/certs/', import.meta.url))
  const https = useHttps
    ? {
        key: fs.readFileSync(`${certDir}dev.key`),
        cert: fs.readFileSync(`${certDir}dev.crt`),
      }
    : undefined

  const apiTarget =
    env.VITE_API_TARGET ||
    (useHttps ? 'https://127.0.0.1:8000' : 'http://127.0.0.1:8000')

  return {
    base: env.VITE_BASE_PATH || '/',
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vue-vendor': ['vue'],
            'element-plus': ['element-plus', '@element-plus/icons-vue'],
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      https,
      // 自签证书仅用于本机回环：secure:false 表示 Vite 不校验后端证书。
      // 生产环境请改用可信证书，并把这里恢复为严格校验。
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
        },
        // Prometheus 是独立 HTTP 服务，前端同源调 /prometheus/* 由 dev server 转发，
        // 避免浏览器跨域限制。生产应改用后端反向代理或网关统一暴露。
        '/prometheus': {
          target: process.env.VITE_PROMETHEUS_TARGET || 'http://127.0.0.1:9090',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/prometheus/, ''),
        },
      },
    },
  }
})
