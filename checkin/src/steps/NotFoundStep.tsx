import { Button } from '@/components/ui/Button'
import { StepHeader } from '@/components/StepHeader'

/**
 * Pelo celular (PRD 048), o número confirmado não tem sessão marcada nesta
 * clínica. Antes do PRD 063 isso caía em "Tudo certo", e a recepção leu como
 * termo em dia: a paciente ficou sem termo. Aqui nada é afirmado; só o
 * caminho de volta.
 */
export function NotFoundStep({ onRestart }: { onRestart: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 text-center">
      <span className="flex h-24 w-24 items-center justify-center rounded-full bg-ink-100">
        <svg viewBox="0 0 52 52" className="h-14 w-14 text-ink-500" aria-hidden>
          <circle cx="23" cy="23" r="12" fill="none" stroke="currentColor" strokeWidth="4" />
          <path d="M32 32l10 10" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
        </svg>
      </span>
      <StepHeader title="Não encontramos sessão para este número">
        Confira o celular digitado ou fale com a recepção.
      </StepHeader>
      <Button variant="secondary" onClick={onRestart} className="w-full max-w-sm">
        Tentar outro número
      </Button>
    </div>
  )
}
