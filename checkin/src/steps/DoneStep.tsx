import { useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { StepHeader } from '@/components/StepHeader'

const AUTO_RESET_MS = 15000

// Posições e cores fixas, não aleatórias: o confete é o mesmo a cada
// conclusão e o teste não depende de sorte.
const CONFETE = Array.from({ length: 26 }, (_, i) => ({
  left: `${(i * 37) % 100}%`,
  delay: `${(i % 7) * 0.09}s`,
  duration: `${2.2 + (i % 5) * 0.3}s`,
  color: ['bg-success-500', 'bg-accent-400', 'bg-accent-500', 'bg-success-600'][i % 4],
  rotate: `${(i * 47) % 360}deg`,
}))

/**
 * Fim do check-in. Uma comemoração curta (o check se desenhando e um confete
 * leve), pedida no teste gravado de 28/10/2026 (PRD 028, M2). Com "reduzir
 * movimento" ligado no aparelho, só o estado final. Volta ao início sozinho:
 * a próxima pessoa não vê nada desta.
 */
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
    <div className="relative flex flex-1 flex-col items-center justify-center gap-10 overflow-hidden text-center">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {CONFETE.map((c, i) => (
          <span
            key={i}
            className={`confete absolute top-0 h-4 w-2.5 rounded-sm ${c.color}`}
            style={{
              left: c.left,
              animationDelay: c.delay,
              animationDuration: c.duration,
              rotate: c.rotate,
            }}
          />
        ))}
      </div>
      <span className="celebra flex h-28 w-28 items-center justify-center rounded-full bg-success-100">
        <svg viewBox="0 0 52 52" className="h-16 w-16 text-success-600" aria-hidden>
          <path
            className="celebra-check"
            fill="none"
            stroke="currentColor"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14 27l8 8 16-17"
          />
        </svg>
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
