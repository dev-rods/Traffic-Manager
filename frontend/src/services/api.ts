import axios, { AxiosError } from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
})

// ── Request interceptor — inject API key ──────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('tm_token')
  if (token) {
    config.headers['x-api-key'] = token
  }
  return config
})

// ── Response interceptor — handle errors globally ─────────────
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tm_token')
      localStorage.removeItem('tm_clinic_id')
      window.location.href = '/login'
    }

    if (error.response && error.response.status >= 500) {
      return Promise.reject(
        new Error('Erro interno do servidor. Tente novamente em instantes.')
      )
    }

    return Promise.reject(error)
  }
)

export default api
