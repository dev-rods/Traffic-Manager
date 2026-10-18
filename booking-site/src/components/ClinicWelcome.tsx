import type { Clinic } from '@/types'

interface ClinicWelcomeProps {
  clinic: Clinic
}

/**
 * Quem está recebendo o agendamento. Fica no topo da lista de serviços e de
 * TODAS as etapas: sem ele, no meio do fluxo a pessoa só via um logo pequeno no
 * cabeçalho e perdia a referência de onde estava agendando (PRD 025, V2).
 */
export function ClinicWelcome({ clinic }: ClinicWelcomeProps) {
  const name = clinic.display_name || clinic.name

  return (
    <div className="flex items-center gap-4">
      <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ink-100 font-display text-xl font-semibold text-ink-600 shadow-card">
        {clinic.logo_url ? (
          <img src={clinic.logo_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span aria-hidden>{name.charAt(0).toUpperCase()}</span>
        )}
      </span>
      <div className="min-w-0">
        <p className="text-sm text-ink-500">Seja bem-vindo(a)</p>
        <h1 className="font-display text-2xl font-bold leading-tight text-ink-900">{name}</h1>
      </div>
    </div>
  )
}
