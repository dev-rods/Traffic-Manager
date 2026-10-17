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

/** Erro da API com a mensagem já normalizada e o status HTTP (quando houve resposta). */
export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status: number | undefined) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// ── Response interceptor — normaliza mensagens de erro da API ─────
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string }>) => {
    const status = error.response?.status
    const apiMessage = error.response?.data?.message
    if (apiMessage) {
      return Promise.reject(new ApiError(apiMessage, status))
    }
    if (status !== undefined && status >= 500) {
      return Promise.reject(new ApiError('Erro interno do servidor. Tente novamente em instantes.', status))
    }
    if (!error.response) {
      return Promise.reject(
        new ApiError('Não foi possível conectar. Verifique sua internet e tente novamente.', undefined)
      )
    }
    return Promise.reject(new ApiError(error.message, status))
  }
)

export default api
