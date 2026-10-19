import { useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { StepHeader } from '@/components/StepHeader'

const AUTO_RESET_MS = 15000

/** Fim do check-in. Volta ao início sozinho: a próxima pessoa não vê nada desta. */
export function DoneStep({
  firstName,
  message,
  onFinish,
}: {
  firstName: string | null
  message: string
  onFinish: () => void
}) {
  useEffect(() => {
    const timer = window.setTimeout(onFinish, AUTO_RESET_MS)
    return () => window.clearTimeout(timer)
  }, [onFinish])

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-10 text-center">
      <span
        aria-hidden
        className="flex h-28 w-28 items-center justify-center rounded-full bg-success-100 text-6xl text-success-600"
      >
        ✓
      </span>
      <StepHeader title={firstName ? `Tudo certo, ${firstName}!` : 'Tudo certo!'}>
        {message}
      </StepHeader>
      <Button variant="secondary" onClick={onFinish} className="w-full max-w-sm">
        Concluir
      </Button>
    </div>
  )
}
