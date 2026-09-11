import axios, { AxiosError } from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL
const BOOKING_API_KEY = import.meta.env.VITE_BOOKING_API_KEY

export const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': BOOKING_API_KEY,
  },
  timeout: 15000,
})

// ── Response interceptor — normaliza mensagens de erro da API ─────
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string }>) => {
    const apiMessage = error.response?.data?.message
    if (apiMessage) {
      return Promise.reject(new Error(apiMessage))
    }
    if (error.response && error.response.status >= 500) {
      return Promise.reject(new Error('Erro interno do servidor. Tente novamente em instantes.'))
    }
    if (!error.response) {
      return Promise.reject(new Error('Não foi possível conectar. Verifique sua internet e tente novamente.'))
    }
    return Promise.reject(error)
  }
)

export default api
