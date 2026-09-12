import { createContext, useContext } from 'react'

export type ToastVariant = 'success' | 'error'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ShowToastOptions {
  message: string
  variant?: ToastVariant
  action?: ToastAction
  /** ms. Padrao: 6000 para success. Erros nunca auto-dispensam. */
  duration?: number
}

export interface ToastContextValue {
  showToast: (options: ShowToastOptions) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast deve ser usado dentro de ToastProvider')
  return context
}
