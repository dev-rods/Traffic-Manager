import { useMemo, useState } from 'react'
import { useAgendaSummary } from '@/hooks/useDashboard'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/Badge'
import { formatCurrency } from '@/utils/formatCurrency'
import type { AgendaDay } from '@/services/reports.service'

type Janela = 'proximos' | 'passados'

const HOJE = new Date().toISOString().slice(0, 10)

function somaDias(iso: string, dias: number) {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + dias)
  return d.toISOString().slice(0, 10)
}

/** `2026-09-23` → `qua, 23/09`. Sem `new Date(iso)` puro: ele lê UTC e volta um dia. */
function rotuloDaData(iso: string) {
  const d = new Date(`${iso}T12:00:00`)
  const semana = d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')
  return `${semana}, ${iso.slice(8, 10)}/${iso.slice(5, 7)}`
}

function horas(minutos: number) {
  if (minutos < 60) return `${minutos}min`
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return m ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`
}

/**
 * Agenda dia a dia, para a gerência.
 *
 * O painel antigo respondia "como foi hoje" e "quantos agendamentos por dia
 * nesta semana". Quem gerencia não pergunta isso: pergunta quanto entra na
 * quinta, quanto está sendo dado de desconto, quantas desmarcaram, e se a sala
 * vai ficar vazia à tarde.
 *
 * Por isso a unidade aqui é a DATA, e o padrão olha para a frente - decisão de
 * gestão se toma sobre o que ainda dá para mudar. Passado fica a um clique,
 * porque fechar o mês também é trabalho de gerência.
 */
export function AgendaPorData() {
  const [janela, setJanela] = useState<Janela>('proximos')

  const periodo = useMemo(
    () =>
      janela === 'proximos'
        ? { start: HOJE, end: somaDias(HOJE, 45) }
        : { start: somaDias(HOJE, -45), end: somaDias(HOJE, -1) },
    [janela],
  )

  const { data, isLoading, isError, error, refetch } = useAgendaSummary(periodo)

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-gray-900">Agenda por data</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            {janela === 'proximos'
              ? 'Próximos 45 dias com agendamento'
              : 'Últimos 45 dias'}
          </p>
        </div>
        <div className="flex gap-1">
          {(
            [
              ['proximos', 'A vir'],
              ['passados', 'Já passou'],
            ] as const
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              onClick={() => setJanela(valor)}
              className={[
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors duration-150',
                janela === valor
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-50 text-gray-500 hover:bg-gray-100',
              ].join(' ')}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </header>

      {isLoading ? (
        <SkeletonTable rows={6} />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar a agenda.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.days.length === 0 ? (
        <EmptyState
          title="Nenhum dia com agendamento"
          description={
            janela === 'proximos'
              ? 'Não há sessões marcadas para os próximos 45 dias.'
              : 'Não houve sessões nos últimos 45 dias.'
          }
        />
      ) : (
        <>
          <TotaisDoPeriodo total={data.total} />
          <TabelaDeDias dias={data.days} />
        </>
      )}
    </section>
  )
}

function TotaisDoPeriodo({ total }: { total: NonNullable<ReturnType<typeof useAgendaSummary>['data']>['total'] }) {
  const itens = [
    { rotulo: 'A faturar', valor: formatCurrency(total.net_cents), destaque: true },
    { rotulo: 'Descontos concedidos', valor: formatCurrency(total.discount_cents) },
    { rotulo: 'Perdido em cancelamentos', valor: formatCurrency(total.lost_cents) },
    { rotulo: 'Sessões', valor: String(total.confirmed) },
    { rotulo: 'Cancelamentos', valor: String(total.cancelled) },
    { rotulo: 'Sala ocupada', valor: horas(total.booked_minutes) },
  ]

  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:grid-cols-6 border-y border-gray-100 py-4">
      {itens.map((i) => (
        <div key={i.rotulo}>
          <p className="text-[11px] uppercase tracking-wide text-gray-400">{i.rotulo}</p>
          <p
            className={[
              'mt-0.5 tabular-nums',
              i.destaque ? 'text-xl font-bold text-gray-900' : 'text-lg font-semibold text-gray-700',
            ].join(' ')}
          >
            {i.valor}
          </p>
        </div>
      ))}
    </div>
  )
}

function TabelaDeDias({ dias }: { dias: AgendaDay[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-[11px] font-medium uppercase tracking-wide text-gray-400">
            <th className="py-2 pr-4">Data</th>
            <th className="py-2 px-3 text-right">Sessões</th>
            <th className="py-2 px-3 text-right">Sala</th>
            <th className="py-2 px-3 text-right">A faturar</th>
            <th className="py-2 px-3 text-right">Desconto</th>
            <th className="py-2 px-3 text-right">Ticket médio</th>
            <th className="py-2 pl-3 text-right">Cancelam.</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {dias.map((d) => (
            <tr key={d.date} className="hover:bg-gray-50/60 transition-colors">
              <td className="py-2.5 pr-4 font-medium text-gray-800 whitespace-nowrap">
                {rotuloDaData(d.date)}
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums text-gray-700">{d.confirmed}</td>
              <td className="py-2.5 px-3 text-right tabular-nums text-gray-500">
                {horas(d.booked_minutes)}
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums font-semibold text-gray-900">
                {formatCurrency(d.net_cents)}
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums text-gray-500">
                {d.discount_cents > 0 ? `- ${formatCurrency(d.discount_cents)}` : '—'}
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums text-gray-500">
                {d.confirmed > 0 ? formatCurrency(d.avg_ticket_cents) : '—'}
              </td>
              <td className="py-2.5 pl-3 text-right">
                {d.cancelled === 0 ? (
                  <span className="text-gray-300">—</span>
                ) : (
                  /* Cancelamento vem com a perda em reais junto: "2" não diz se
                     o dia perdeu R$ 90 ou R$ 900. */
                  <span className="inline-flex items-center gap-1.5">
                    <span className="text-xs tabular-nums text-gray-400">
                      - {formatCurrency(d.lost_cents)}
                    </span>
                    <Badge variant={d.cancellation_rate >= 30 ? 'danger' : 'warning'}>
                      {d.cancelled}
                    </Badge>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
