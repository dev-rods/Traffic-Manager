import { Input } from '@/components/ui/Input'
import { explicaDesfecho, type Desfecho } from '@/lib/desfecho'

interface DesfechoFieldProps {
  /** O que o backend fará sozinho, pela antecedência. */
  automatico: Desfecho
  valor: Desfecho
  onChange: (d: Desfecho) => void
  motivo: string
  onMotivo: (m: string) => void
}

const OPCOES: ReadonlyArray<{ key: Desfecho; label: string }> = [
  { key: 'NO_SHOW', label: 'Falta' },
  { key: 'CANCELLED', label: 'Cancelamento' },
]

/**
 * O desfecho do agendamento que vai ser encerrado (PRD 054, decisão 2).
 *
 * A regra automática aparece primeiro e já vem marcada. A recepção pode
 * trocar ("desmarcou por doença"), e aí o motivo é obrigatório: fica gravado
 * com quem trocou. Bot e site não têm esta escolha.
 */
export function DesfechoField({ automatico, valor, onChange, motivo, onMotivo }: DesfechoFieldProps) {
  const diverge = valor !== automatico
  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-700">{explicaDesfecho(automatico)}</p>
      <div>
        <span className="text-xs font-medium text-gray-500 block mb-1.5">Registrar como</span>
        <div className="flex gap-2" role="group" aria-label="Registrar como">
          {OPCOES.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={valor === key}
              onClick={() => onChange(key)}
              className={[
                'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border',
                valor === key
                  ? key === 'NO_SHOW'
                    ? 'bg-red-50 border-red-300 text-red-700'
                    : 'bg-gray-900 border-gray-900 text-white'
                  : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600',
              ].join(' ')}
            >
              {label}
              {key === automatico && <span className="ml-1 font-normal opacity-70">(automático)</span>}
            </button>
          ))}
        </div>
      </div>
      {diverge && (
        <Input
          label="Motivo (obrigatório ao trocar o desfecho)"
          value={motivo}
          maxLength={200}
          onChange={(e) => onMotivo(e.target.value)}
          placeholder="Ex.: avisou doença com atestado"
        />
      )}
    </div>
  )
}
