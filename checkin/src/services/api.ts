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
  // Campo apontado pelo backend num 400 de validação (ficha de anamnese,
  // PRD 038), para a tela marcar a pergunta certa.
  readonly field: string | null

  constructor(message: string, status: number | undefined, field: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.field = field
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string; field?: string }>) => {
    const status = error.response?.status
    const message = error.response?.data?.message
    if (message) {
      return Promise.reject(new ApiError(message, status, error.response?.data?.field ?? null))
    }
    if (!error.response) {
      return Promise.reject(
        new ApiError('Sem conexão com a internet. Chame a recepção, por favor.', undefined)
      )
    }
    return Promise.reject(new ApiError('Algo deu errado. Tente de novo.', status))
  }
)
