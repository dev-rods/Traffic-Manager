import { useCallback, useMemo, useRef, useState } from 'react'
import { ToastContext } from './toastContext'
import type { ShowToastOptions, ToastVariant } from './toastContext'

interface ToastItem extends ShowToastOptions {
  id: number
  variant: ToastVariant
}

const DEFAULT_DURATION = 6000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    ({ message, variant = 'success', action, duration }: ShowToastOptions) => {
      const id = nextId.current++
      setToasts((current) => [...current, { id, message, variant, action, duration }])

      // Erro fica ate o usuario dispensar: precisa ser legivel.
      if (variant !== 'error') {
        const timer = setTimeout(() => dismiss(id), duration ?? DEFAULT_DURATION)
        timers.current.set(id, timer)
      }
    },
    [dismiss],
  )

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-[100] flex flex-col gap-3">
        {toasts.map((toast) => (
          <ToastCard
            key={toast.id}
            toast={toast}
            onDismiss={() => dismiss(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const isError = toast.variant === 'error'

  return (
    <div
      role="status"
      aria-live={isError ? 'assertive' : 'polite'}
      className={[
        'pointer-events-auto flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg',
        'motion-safe:animate-[toast-in_200ms_cubic-bezier(0.25,1,0.5,1)]',
        'max-w-sm border',
        isError ? 'bg-red-50 border-red-200 text-red-800' : 'bg-gray-800 border-gray-700 text-gray-50',
      ].join(' ')}
    >
      {/* Icone alem da cor: o estado nao pode depender so de cor. */}
      <span aria-hidden className="shrink-0 text-base leading-none">
        {isError ? '⚠' : '✓'}
      </span>

      <p className="flex-1 text-sm">{toast.message}</p>

      {toast.action && (
        <button
          type="button"
          onClick={() => {
            toast.action?.onClick()
            onDismiss()
          }}
          className={[
            'shrink-0 rounded px-2 py-1 text-xs font-semibold uppercase tracking-wide',
            'min-h-[44px] transition-colors duration-150',
            isError ? 'text-red-700 hover:bg-red-100' : 'text-brand-300 hover:bg-gray-700',
          ].join(' ')}
        >
          {toast.action.label}
        </button>
      )}

      <button
        type="button"
        onClick={onDismiss}
        aria-label="Fechar notificação"
        className={[
          'shrink-0 text-lg leading-none transition-colors duration-150',
          isError ? 'text-red-400 hover:text-red-700' : 'text-gray-400 hover:text-gray-100',
        ].join(' ')}
      >
        &times;
      </button>
    </div>
  )
}
