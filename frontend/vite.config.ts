import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  css: {
    preprocessorOptions: {
      scss: {
        // 静音 sass 旧版 API 的告警（Geeker 模板里用了 @use 的写法）
        silenceDeprecations: ['legacy-js-api', 'import'],
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 【前后端分离的关键】
    // 浏览器只认识 "同源" 请求：页面在 localhost:5173，
    // 直接 fetch("http://127.0.0.1:8003/...") 会被浏览器拦截（CORS）。
    //
    // Vite dev server 充当反向代理：浏览器请求 localhost:5173/api/xxx，
    // 由 Vite 在服务端转发到 127.0.0.1:8003/xxx。
    // 浏览器全程只跟 5173 说话 -> 同源 -> 不会被拦截，
    // 而 FastAPI 后端【一行都不用改】（不用加 CORSMiddleware）。
    //
    // 生产环境同理：把 /api 用 Nginx 反代到后端即可，前端代码零改动。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
        // 去掉 /api 前缀，因为后端的路径是 /student/xxx 而不是 /api/student/xxx
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // 知识库小助手（kb_assistant/ 独立服务，默认端口 8010）
      // 注意这里【不 rewrite】：后端的路由本来就是 /kb/chat、/kb/health，
      // 去掉前缀反而对不上。前端请求 /kb/xxx -> 小助手收到 /kb/xxx。
      '/kb': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
})
