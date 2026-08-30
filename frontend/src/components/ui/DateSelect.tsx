import { useMemo } from 'react'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import { formatDateOption } from '@/utils/formatDateOption'
import { todayStr } from '@/utils/dateHelpers'

interface DateSelectProps {
  value: string
  onChange: (date: string) => void
  label?: string
  /** Datas passadas entram na lista. Necessário ao editar um agendamento antigo. */
  includePast?: boolean
}

/**
 * Escolha de data restrita ao que a clínica cadastrou em Horários.
 *
 * Antes era um input de data livre: dava para marcar sessão num dia sem
 * atendimento, e a pessoa só descobria ao ver "nenhum horário disponível".
 * O sistema já sabe quais datas existem - oferecer o calendário inteiro
 * transferia esse trabalho para quem agenda.
 */
export function DateSelect({ value, onChange, label = 'Data', includePast = false }: DateSelectProps) {
  const { data, isLoading } = useAvailabilityRules()

  const datas = useMemo(() => {
    const hoje = todayStr()
    const cadastradas = (data?.data ?? [])
      .filter((r) => r.rule_date !== null)
      .map((r) => r.rule_date as string)
      .filter((d) => includePast || d >= hoje)

    // A data já escolhida entra mesmo fora do filtro, senão editar um
    // agendamento antigo apagaria silenciosamente a data dele.
    if (value && !cadastradas.includes(value)) cadastradas.push(value)

    return [...new Set(cadastradas)].sort()
  }, [data, includePast, value])

  return (
    <div>
      <label htmlFor="data-atendimento" className="text-xs font-medium text-gray-500 block mb-1.5">
        {label}
      </label>
      <select
        id="data-atendimento"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading || datas.length === 0}
        className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:bg-gray-50 disabled:text-gray-400"
      >
        <option value="">
          {isLoading ? 'Carregando datas...' : datas.length === 0 ? 'Nenhuma data cadastrada' : 'Selecione...'}
        </option>
        {datas.map((d) => (
          <option key={d} value={d}>{formatDateOption(d)}</option>
        ))}
      </select>
      {!isLoading && datas.length === 0 && (
        <p className="text-xs text-gray-500 mt-1.5">
          Cadastre os dias de atendimento em <span className="font-medium">Horários</span> para poder agendar.
        </p>
      )}
    </div>
  )
}
