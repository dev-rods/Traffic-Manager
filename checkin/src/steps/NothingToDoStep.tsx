import { StepHeader } from '@/components/StepHeader'

/**
 * Pelo celular (PRD 048), quem entra sem sessão com documento pendente: já
 * assinou, está em papel, foi dispensada ou não tem sessão marcada. Nada a
 * fazer aqui; o check-in continua sendo no dia, na recepção.
 */
export function NothingToDoStep({ firstName }: { firstName: string | null }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
      <span className="flex h-24 w-24 items-center justify-center rounded-full bg-success-100">
        <svg viewBox="0 0 52 52" className="h-14 w-14 text-success-600" aria-hidden>
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14 27l8 8 16-17"
          />
        </svg>
      </span>
      <StepHeader title={firstName ? `Tudo certo, ${firstName}` : 'Tudo certo'}>
        Não há nada para preencher agora. No dia da sessão, é só chegar e fazer o check-in na
        recepção.
      </StepHeader>
    </div>
  )
}
