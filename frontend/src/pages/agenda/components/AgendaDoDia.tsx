import { timeToMinutes } from '@/utils/dateHelpers'
import {
  comoHora,
  duracaoPorExtenso,
  janelaDoDia,
  vaosLivres,
  type Vao,
} from '@/lib/expediente'
import type { Appointment, AvailabilityRule } from '@/types'

interface AgendaDoDiaProps {
  dia: string
  appointments: Appointment[]
  /**
   * As regras de horário da clínica. Sem elas os vãos não aparecem - e é o
   * comportamento certo: inventar um fechamento seria oferecer horário que a
   * clínica não atende.
   */
  rules: AvailabilityRule[]
  onAppointmentClick: (appointment: Appointment, rect: DOMRect) => void
}

/** Uma linha da lista: ou um atendimento, ou o buraco antes dele. */
type Item =
  | { tipo: 'atendimento'; appointment: Appointment }
  | { tipo: 'vao'; vao: Vao }

/**
 * Intercala os vaos entre os atendimentos, na ordem do relogio.
 *
 * Feito aqui e nao no `map` do JSX porque a ordem e a informacao: um vao que
 * apareca no lugar errado da lista mente sobre quando o horario abre.
 */
function montaLinhas(
  doDia: Appointment[],
  janela: { inicio: number; fim: number } | null,
): Item[] {
  const vaos = janela ? vaosLivres(doDia, janela) : []

  const linhas: Item[] = [
    ...doDia.map((a) => ({ tipo: 'atendimento' as const, appointment: a })),
    ...vaos.map((v) => ({ tipo: 'vao' as const, vao: v })),
  ]

  return linhas.sort((x, y) => {
    const inicio = (i: Item) =>
      i.tipo === 'vao' ? i.vao.inicio : timeToMinutes(i.appointment.start_time)
    // Empate: o vao vem primeiro. Ele TERMINA onde o atendimento comeca, entao
    // so pode estar acima - o contrario faria a lista voltar no tempo.
    return inicio(x) - inicio(y) || (x.tipo === 'vao' ? -1 : 1)
  })
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
 * O que lhe faltava era o **buraco livre**. Na grade ele se vê sozinho, como
 * espaço em branco; numa lista de atendimentos, some. Descobrir que das 10h às
 * 14h não há nada exigia subtrair horários de cabeça, linha a linha - e é
 * justamente o que se quer saber com o celular na mão, no balcão, com a
 * paciente esperando.
 *
 * Os vãos saem do horário REAL da clínica naquele dia - as mesmas regras de
 * `availability_rules` que fazem o dia aparecer na agenda. Sem regra para o
 * dia, nenhum vão é mostrado: dizer "livre até 22:00" numa clínica que fecha
 * às 19h é pior do que não dizer nada.
 */
export function AgendaDoDia({ dia, appointments, rules, onAppointmentClick }: AgendaDoDiaProps) {
  const janela = janelaDoDia(rules, dia)
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
      {montaLinhas(doDia, janela).map((item) =>
        item.tipo === 'vao' ? (
          <LinhaLivre key={`livre-${item.vao.inicio}`} vao={item.vao} />
        ) : (
          <LinhaDaAgenda
            key={item.appointment.id}
            appointment={item.appointment}
            onClick={onAppointmentClick}
          />
        ),
      )}
    </ul>
  )
}

/**
 * Um buraco na agenda.
 *
 * Deliberadamente mais leve que um atendimento: fundo listrado, sem faixa
 * colorida, texto menor. A lista e sobre o que esta marcado - o vao e o
 * contorno disso, e competir em peso com as sessoes inverteria a leitura.
 *
 * Nao e botao. Tocar aqui para criar agendamento seria o gesto obvio, mas o
 * horario livre na tela nao e o mesmo que horario agendavel: falta o
 * profissional, a sala e a duracao do servico, que a API de `available-slots`
 * conhece e esta conta nao. Um toque que abrisse o formulario ja preenchido
 * prometeria um horario que o servidor pode recusar.
 */
function LinhaLivre({ vao }: { vao: Vao }) {
  const minutos = vao.fim - vao.inicio

  return (
    <li className="flex items-center gap-3 bg-[repeating-linear-gradient(135deg,transparent,transparent_6px,rgb(0_0_0/0.02)_6px,rgb(0_0_0/0.02)_12px)] px-3 py-2">
      <span aria-hidden className="w-1 self-stretch" />
      <span className="w-12 flex-shrink-0 text-xs font-medium tabular-nums text-gray-400">
        {comoHora(vao.inicio)}
      </span>
      <span className="text-xs text-gray-400">
        Livre até {comoHora(vao.fim)}
        <span className="text-gray-300"> · {duracaoPorExtenso(minutos)}</span>
      </span>
    </li>
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
  const faltou = a.status === 'NO_SHOW'

  return (
    <li>
      <button
        type="button"
        onClick={(e) => onClick(a, e.currentTarget.getBoundingClientRect())}
        className={[
          'flex w-full items-start gap-3 px-3 py-3 text-left transition-colors active:bg-gray-50',
          // O mesmo tratamento da grade do desktop, pela mesma razao: a cor
          // ja carrega parceria e estreia, e riscado le-se sem depender dela.
          faltou && 'opacity-60 saturate-50',
        ].filter(Boolean).join(' ')}
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
            <span className={faltou ? 'font-medium text-gray-900 line-through' : 'font-medium text-gray-900'}>
              {nome}
            </span>
            {faltou && (
              <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] font-semibold text-gray-600">
                FALTOU
              </span>
            )}
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
