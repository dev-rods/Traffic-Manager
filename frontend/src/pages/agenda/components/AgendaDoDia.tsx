import { timeToMinutes } from '@/utils/dateHelpers'
import type { Appointment } from '@/types'

interface AgendaDoDiaProps {
  dia: string
  appointments: Appointment[]
  onAppointmentClick: (appointment: Appointment, rect: DOMRect) => void
}

/**
 * A agenda do dia em celular: uma lista cronológica, e não a grade.
 *
 * A grade foi medida e reprovada para esta tela (spec 015, seção 2). Dois
 * números decidiram:
 *
 *   - 15 horas x 112px = 1680px, ou 2,6 telas de rolagem para ver UM dia
 *   - um alvo de toque de 44px vale 23,6 minutos de agenda, então uma sessão
 *     de 10 minutos precisaria inflar até ocupar 23,6 - e o `distribuiEmColunas`
 *     jogaria duas sessões seguidas em colunas separadas, partindo ao meio uma
 *     largura que já é estreita
 *
 * A lista não tem nenhum dos dois problemas: cada linha é naturalmente maior
 * que 44px, nada se sobrepõe, e só aparece o que existe em vez de quinze horas
 * de grade vazia.
 *
 * O que ela não mostra é **buraco livre**. Quem vai agendar usa o botão de
 * novo agendamento, que pergunta o horário à API de `available-slots` - ela
 * conhece os vãos melhor que o olho.
 */
export function AgendaDoDia({ dia, appointments, onAppointmentClick }: AgendaDoDiaProps) {
  const doDia = appointments
    .filter((a) => a.appointment_date === dia && a.status !== 'CANCELLED')
    .sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time))

  if (doDia.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-white px-4 py-10 text-center">
        <p className="text-sm text-gray-500">Nenhum atendimento neste dia.</p>
      </div>
    )
  }

  return (
    <ul className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {doDia.map((a) => (
        <LinhaDaAgenda key={a.id} appointment={a} onClick={onAppointmentClick} />
      ))}
    </ul>
  )
}

function LinhaDaAgenda({
  appointment: a,
  onClick,
}: {
  appointment: Appointment
  onClick: (a: Appointment, rect: DOMRect) => void
}) {
  const nome = a.patient_name || a.full_name || 'Sem nome'
  const daParceria = a.discount_reason === 'partnership'

  return (
    <li>
      <button
        type="button"
        onClick={(e) => onClick(a, e.currentTarget.getBoundingClientRect())}
        className="flex w-full items-start gap-3 px-3 py-3 text-left transition-colors active:bg-gray-50"
      >
        {/* A faixa colorida carrega o mesmo significado da borda esquerda na
            grade do desktop - parceria vence estreia, pela mesma razão de lá:
            as duas quase sempre andam juntas e a que muda o atendimento é a
            parceria. */}
        <span
          aria-hidden
          className={[
            'mt-0.5 w-1 self-stretch rounded-full',
            daParceria
              ? 'bg-amber-400'
              : a.is_first_visit
                ? 'bg-fuchsia-500'
                : 'bg-brand-500',
          ].join(' ')}
        />

        <span className="w-12 flex-shrink-0 pt-0.5 text-sm font-semibold tabular-nums text-gray-800">
          {a.start_time.slice(0, 5)}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <span className="font-medium text-gray-900">{nome}</span>
            {daParceria && (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                PARCERIA
              </span>
            )}
            {a.is_first_visit && !daParceria && (
              <span className="rounded bg-fuchsia-100 px-1.5 py-0.5 text-[10px] font-semibold text-fuchsia-700">
                1ª VEZ
              </span>
            )}
          </span>

          {/* Áreas e duração na própria linha, e não atrás de um toque: numa
              tela pequena são a informação que decide o atendimento, e foi
              exatamente o que faltava no popover até 21/09. */}
          {a.areas && (
            <span className="mt-0.5 block text-xs leading-snug text-gray-500">
              {a.areas}
            </span>
          )}
          {a.duration_minutes != null && (
            <span className="mt-0.5 block text-xs text-gray-400">
              {a.duration_minutes} min
              {a.manual_duration_minutes != null && ' · ajustada'}
            </span>
          )}
        </span>
      </button>
    </li>
  )
}
