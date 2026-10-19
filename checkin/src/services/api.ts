import axios, { AxiosError } from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': import.meta.env.VITE_BOOKING_API_KEY,
  },
  timeout: 20000,
})

/** Erro da API com a mensagem para a tela e o status HTTP (quando houve resposta). */
export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status: number | undefined) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string }>) => {
    const status = error.response?.status
    const message = error.response?.data?.message
    if (message) return Promise.reject(new ApiError(message, status))
    if (!error.response) {
      return Promise.reject(
        new ApiError('Sem conexão com a internet. Chame a recepção, por favor.', undefined)
      )
    }
    return Promise.reject(new ApiError('Algo deu errado. Tente de novo.', status))
  }
)
