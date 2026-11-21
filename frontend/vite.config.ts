import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

// Em produção a Vercel reescreve /api para o API Gateway (vercel.json, PRD
// 055). Em `npm run dev` o Vite faz o mesmo papel: o alvo é o stage de dev,
// salvo VITE_API_PROXY_TARGET dizer outro. Assim o browser nunca fala com o
// API Gateway de outra origem, e a API não precisa de CORS.
const API_DEV = 'https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const alvo = new URL(env.VITE_API_PROXY_TARGET || API_DEV)
  const prefixo = alvo.pathname.replace(/\/$/, '')
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: alvo.origin,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, prefixo),
        },
      },
    },
  }
})
