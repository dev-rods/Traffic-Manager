import { Input } from '@/components/ui/Input'
import { ehHorarioValido } from '@/lib/horario'

interface TimeFieldProps {
  /** Horário escolhido, em HH:MM. */
  value: string
  onChange: (time: string) => void
  /** Horários sugeridos pela grade da clínica. */
  slots: string[]
  loading?: boolean
  /** Sem data e serviço não há o que sugerir nem duração para calcular o fim. */
  enabled: boolean
}

/**
 * Escolha de horário: os sugeridos pela grade, e um campo para digitar outro.
 *
 * O campo manual existe porque a grade não cobre tudo que a clínica faz. Encaixe
 * fora do padrão, atendimento que entrou por telefone, horário que abriu com um
 * cancelamento que ninguém sincronizou - antes, nada disso dava para marcar
 * pelo painel, e a atendente ficava sem saída dentro da própria ferramenta.
 *
 * O backend aceita: ele valida conflito com agendamento existente, não a grade.
 * Um horário digitado que colida com outra sessão volta 409 e a tela mostra o
 * erro; um que só esteja fora da grade é aceito, que é a intenção.
 *
 * Por isso o aviso de "fora dos sugeridos" é informativo e não bloqueia. Quem
 * digitou um horário fora da lista quase sempre sabe o que está fazendo - o
 * aviso serve para o caso em que foi engano de digitação.
 */
export function TimeField({ value, onChange, slots, loading, enabled }: TimeFieldProps) {
  const forcado = enabled && ehHorarioValido(value) && !slots.includes(value)

  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1.5">Horário</label>

      {!enabled ? (
        <p className="text-sm text-gray-300 py-3">Selecione data e serviço para ver horários</p>
      ) : (
        <div className="space-y-2.5">
          {loading ? (
            <div className="flex items-center gap-2 py-3">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-400">Carregando horários...</span>
            </div>
          ) : slots.length === 0 ? (
            // Sem sugestão o campo manual deixa de ser alternativa e vira o
            // único caminho - é justamente o dia em que a atendente mais
            // precisa dele.
            <p className="text-sm text-gray-400">
              Nenhum horário sugerido para esta data. Digite abaixo se quiser marcar mesmo assim.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
              {slots.map((slot) => (
                <button
                  key={slot}
                  type="button"
                  onClick={() => onChange(slot)}
                  className={[
                    'px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                    value === slot
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                  ].join(' ')}
                >
                  {slot}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2.5">
            <span className="text-xs text-gray-400 shrink-0">Ou digite:</span>
            <Input
              type="time"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              className="w-32"
              aria-label="Horário manual"
            />
            {forcado && (
              <span className="text-xs text-amber-600">Fora dos horários sugeridos</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
