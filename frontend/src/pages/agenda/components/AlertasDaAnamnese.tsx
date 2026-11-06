import type { AlertaDaAnamnese } from '@/types'

interface AlertasDaAnamneseProps {
  alertas: AlertaDaAnamnese[]
  compacto?: boolean
}

/**
 * Os "Sim" da ficha de anamnese que mudam a conduta (PRD 038). Vêm prontos
 * do backend e são EXIBIDOS, nunca interpretados: nada aqui bloqueia a
 * sessão. Quem decide contraindicação é a profissional.
 */
export function AlertasDaAnamnese({ alertas, compacto = false }: AlertasDaAnamneseProps) {
  if (alertas.length === 0) return null
  return (
    <div
      role="list"
      aria-label="Alertas da anamnese"
      className={`rounded-lg border border-red-200 bg-red-50 ${compacto ? 'px-2.5 py-1.5' : 'px-3 py-2'}`}
    >
      <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-red-700">
        Alertas da anamnese
      </p>
      <ul className="space-y-0.5">
        {alertas.map((a) => (
          <li key={a.key} role="listitem" className="flex items-start gap-1.5 text-xs text-red-700">
            <span aria-hidden className="mt-0.5 shrink-0 font-bold">
              !
            </span>
            <span>{a.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
