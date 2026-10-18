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

interface ApiErrorBody {
  message?: string
  code?: string
  existingCount?: number
}

/**
 * Erro da API com a mensagem já normalizada, o status HTTP (quando houve
 * resposta) e o `code` que alguns erros trazem para o front distinguir casos
 * de mesmo status (ex.: os dois 409 da criação).
 */
export class ApiError extends Error {
  readonly status: number | undefined
  readonly code: string | undefined
  readonly body: ApiErrorBody | undefined

  constructor(message: string, status: number | undefined, body?: ApiErrorBody) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = body?.code
    this.body = body
  }
}

// ── Response interceptor — normaliza mensagens de erro da API ─────
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status
    const body = error.response?.data
    const apiMessage = body?.message
    if (apiMessage) {
      return Promise.reject(new ApiError(apiMessage, status, body))
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
