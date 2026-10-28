import { useState } from 'react'
import { useCaixa, useEstornar, useReceberDinheiro } from '@/hooks/useCaixa'
import { useToast } from '@/components/ui/toastContext'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { formatCurrency } from '@/utils/formatCurrency'
import { METODOS, METODO_LABEL, dataDe, horaDe, situacaoDoPagamento } from '@/utils/pagamento'
import { FAIXAS, intervaloDa, type Faixa } from '@/utils/caixa'
import type { CaixaPayment, CaixaPending, CaixaResumo } from '@/services/caixa.service'
import { KpiCard } from './KpiCard'

function dataCurta(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

function mensagemDoErro(erro: unknown, padrao: string): string {
  return (erro as { response?: { data?: { message?: string } } })?.response?.data?.message ?? padrao
}

/**
 * O caixa: quanto entrou, por onde, e o que falta receber (PRD 026).
 *
 * "Recebido" é pela hora em que o dinheiro entrou; "Previsto" é pela data da
 * sessão. É o que permite bater com o extrato do Asaas e com a gaveta no fim
 * do dia - e é por isso que a diferença entre os dois não é "o que falta". O
 * que falta é a lista de pendências.
 */
export function CaixaPanel() {
  const [faixa, setFaixa] = useState<Faixa>('hoje')
  const [de, ate] = intervaloDa(faixa)
  const { data, isLoading, isError, error, refetch } = useCaixa(de, ate)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-500">
          {de === ate ? dataCurta(de) : `${dataCurta(de)} a ${dataCurta(ate)}`}
        </p>
        <div className="flex rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          {FAIXAS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFaixa(f.value)}
              className={[
                'px-4 py-2 text-sm font-medium transition-colors cursor-pointer',
                faixa === f.value ? 'bg-brand-500 text-white' : 'text-gray-600 hover:bg-gray-50',
              ].join(' ')}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : isError || !data ? (
        <ErrorState
          message={mensagemDoErro(error, 'Erro ao carregar o caixa.')}
          onRetry={() => refetch()}
        />
      ) : (
        <CaixaConteudo data={data} />
      )}
    </div>
  )
}

function CaixaConteudo({ data }: { data: CaixaResumo }) {
  const t = data.totals
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          label="Recebido"
          value={formatCurrency(t.receivedCents)}
          valueColor="text-emerald-600"
          subtext={`${data.payments.length} pagamento(s) no período`}
          subtextColor="text-gray-400"
        />
        <KpiCard
          label="Previsto pelas sessões"
          value={formatCurrency(t.expectedCents)}
          subtext={`${data.days.reduce((n, d) => n + d.sessions, 0)} sessão(ões) confirmada(s)`}
          subtextColor="text-gray-400"
        />
        <KpiCard
          label="Falta receber"
          value={formatCurrency(t.pendingCents)}
          valueColor={t.pendingCount > 0 ? 'text-amber-600' : 'text-gray-800'}
          subtext={
            t.pendingCount > 0 ? `${t.pendingCount} sessão(ões) até hoje` : 'Nada pendente'
          }
          subtextColor="text-gray-400"
        />
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Por forma de pagamento</h2>
        <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {METODOS.map((m) => (
            <div key={m}>
              <dt className="text-sm text-gray-400">{METODO_LABEL[m]}</dt>
              <dd className="text-lg font-semibold text-gray-800 tabular-nums">
                {formatCurrency(t.byMethod[m].cents)}
              </dd>
              <dd className="text-xs text-gray-400">{t.byMethod[m].count} pagamento(s)</dd>
            </div>
          ))}
        </dl>
      </div>

      {data.refundsPending.length > 0 ? <EstornosPendentes pagamentos={data.refundsPending} /> : null}
      <Pendencias pendentes={data.pending} />
      <Recebimentos data={data} />
    </>
  )
}

function Pendencias({ pendentes }: { pendentes: CaixaPending[] }) {
  const receber = useReceberDinheiro()
  const { showToast } = useToast()

  return (
    <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <h2 className="border-b border-gray-100 px-5 py-4 text-base font-semibold text-gray-800">
        Falta receber
      </h2>
      {pendentes.length === 0 ? (
        <p className="px-5 py-6 text-sm text-gray-500">
          Todas as sessões até hoje neste período estão pagas.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {pendentes.map((p) => {
            const situacao = situacaoDoPagamento(p.paymentStatus, p.method)
            return (
              <li key={p.appointmentId} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <span className="w-24 text-sm tabular-nums text-gray-500">
                  {dataCurta(p.date)} {p.startTime}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-800">
                  {p.name ?? 'Sem nome'}
                  {p.checkedIn ? (
                    <span className="ml-2 text-xs font-normal text-gray-400">check-in feito</span>
                  ) : null}
                </span>
                <span className="text-sm text-amber-600">{situacao.label}</span>
                <span className="w-24 text-right text-sm font-semibold tabular-nums text-gray-800">
                  {formatCurrency(p.amountCents)}
                </span>
                {p.paymentStatus === 'AWAITING_CASH' && p.paymentId ? (
                  <button
                    type="button"
                    disabled={receber.isPending}
                    onClick={() =>
                      receber.mutate(p.paymentId as string, {
                        onSuccess: () => showToast({ message: 'Pagamento em dinheiro registrado' }),
                        onError: (erro) =>
                          showToast({
                            message: mensagemDoErro(erro, 'Não foi possível registrar o pagamento.'),
                            variant: 'error',
                          }),
                      })
                    }
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60 cursor-pointer"
                  >
                    Recebi em dinheiro
                  </button>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function Recebimentos({ data }: { data: CaixaResumo }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <h2 className="border-b border-gray-100 px-5 py-4 text-base font-semibold text-gray-800">
        Recebimentos
      </h2>
      {data.payments.length === 0 ? (
        <p className="px-5 py-6 text-sm text-gray-500">
          Nenhum pagamento entrou neste período. Os pagamentos feitos no check-in do iPad aparecem
          aqui.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {data.payments.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <span className="w-24 text-sm tabular-nums text-gray-500">
                {dataDe(p.paidAt)} {horaDe(p.paidAt)}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-800">
                {p.name ?? 'Sem nome'}
                <span className="ml-2 text-xs font-normal text-gray-400">
                  sessão {dataCurta(p.appointmentDate)} {p.startTime}
                </span>
                {p.simulated ? (
                  <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                    TESTE
                  </span>
                ) : null}
                {p.appointmentCancelled ? (
                  <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                    SESSÃO CANCELADA
                  </span>
                ) : null}
              </span>
              <span className="text-sm text-gray-600">{METODO_LABEL[p.method]}</span>
              <span className="w-24 text-right text-sm font-semibold tabular-nums text-emerald-600">
                {formatCurrency(p.amountCents)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * Dinheiro que entrou de sessão que não vai acontecer (PRD 028, M7). Estornar
 * é decisão humana (pode virar crédito para outra sessão), mas não pode
 * passar despercebido. Pix e cartão voltam pelo Asaas; dinheiro fica
 * registrado como estornado e a devolução é feita em mão.
 */
function EstornosPendentes({ pagamentos }: { pagamentos: CaixaPayment[] }) {
  const estornar = useEstornar()
  const { showToast } = useToast()
  const [confirmando, setConfirmando] = useState<string | null>(null)

  function confirmar(p: CaixaPayment) {
    estornar.mutate(p.id, {
      onSuccess: (r) => {
        setConfirmando(null)
        showToast({
          message:
            p.method === 'CASH'
              ? 'Estorno registrado. Devolva o dinheiro na recepção.'
              : r.refundNeedsAuthorization
                ? 'Estorno pedido ao Asaas. Autorize no app ou no painel do Asaas para o dinheiro voltar.'
                : 'Estorno enviado ao Asaas.',
        })
      },
      onError: (erro) =>
        showToast({
          message: mensagemDoErro(erro, 'Não foi possível estornar.'),
          variant: 'error',
        }),
    })
  }

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50 shadow-sm">
      <h2 className="border-b border-amber-200 px-5 py-4 text-base font-semibold text-amber-800">
        Estornos pendentes
        <span className="ml-2 text-sm font-normal text-amber-700">
          pagamentos de sessões canceladas
        </span>
      </h2>
      <ul className="divide-y divide-amber-100">
        {pagamentos.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-800">
              {p.name ?? 'Sem nome'}
              <span className="ml-2 text-xs font-normal text-gray-500">
                sessão {dataCurta(p.appointmentDate)} {p.startTime} · pago em {dataDe(p.paidAt)}
              </span>
            </span>
            <span className="text-sm text-gray-600">{METODO_LABEL[p.method]}</span>
            <span className="w-24 text-right text-sm font-semibold tabular-nums text-gray-800">
              {formatCurrency(p.amountCents)}
            </span>
            {confirmando === p.id ? (
              <span className="flex gap-2">
                <button
                  type="button"
                  disabled={estornar.isPending}
                  onClick={() => confirmar(p)}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60 cursor-pointer"
                >
                  {estornar.isPending ? 'Estornando…' : 'Confirmar estorno'}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmando(null)}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-amber-100 cursor-pointer"
                >
                  Voltar
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmando(p.id)}
                className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-semibold text-amber-800 hover:bg-amber-100 cursor-pointer"
              >
                Estornar
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

