import { Fragment, useMemo, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useLeads } from '@/hooks/useLeads'
import { useClinic } from '@/hooks/useClinic'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import { useSelection } from '@/hooks/useSelection'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Pagination } from '@/components/ui/Pagination'
import { formatPhone } from '@/utils/formatPhone'
import { formatDateBR } from '@/utils/formatDate'
import { proximasDatas } from '@/utils/proximasDatas'
import { BatchMessageModal, type Destinatario } from '@/pages/pacientes/components/BatchMessageModal'
import type { Lead, LeadStage } from '@/types'
import { ChipsDeEstagio } from './ChipsDeEstagio'
import { EstagioBadge } from './EstagioBadge'
import { PopoverDeEstagio } from './PopoverDeEstagio'
import { ORIGENS, rotuloDaOrigem } from './estagios'

const POR_PAGINA_PADRAO = 25

function ultimaMensagem(lead: Lead): string {
  if (!lead.ultima_mensagem_em) return '-'
  const quem = lead.ultima_mensagem_de === 'LEAD' ? 'do lead' : 'nossa'
  return `${formatDateBR(lead.ultima_mensagem_em)} · ${quem}`
}

/**
 * A fila da semana (PRD 057): cada lead com o estagio que a regra, o modelo ou
 * a equipe deu; chips para filtrar, correcao inline e disparo em lote.
 *
 * STAFF ve e corrige. O disparo e ADMIN, porque `POST /send` e ADMIN.
 */
export function CrmPage() {
  const { ehAdmin } = useAuth()
  const [estagios, setEstagios] = useState<LeadStage[]>([])
  const [origens, setOrigens] = useState<string[]>([])
  const [mostrarMais, setMostrarMais] = useState(false)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(POR_PAGINA_PADRAO)
  const [editando, setEditando] = useState<string | null>(null)
  const [disparoAberto, setDisparoAberto] = useState(false)

  const params = {
    stage: estagios.length ? estagios.join(',') : undefined,
    source: origens.length ? origens.join(',') : undefined,
    orderBy: 'dias_parado' as const,
    limit: perPage,
    offset: (page - 1) * perPage,
  }
  const { data, isLoading, isError, error, refetch } = useLeads(params)
  const { data: clinic } = useClinic()
  const { data: rulesData } = useAvailabilityRules()
  const availableDates = useMemo(
    () => proximasDatas(rulesData?.data, clinic?.max_future_dates),
    [rulesData, clinic],
  )

  const leads = data?.leads ?? []
  const total = data?.total ?? 0
  const contagem = data?.totals.por_estagio ?? {}
  const selecao = useSelection<Lead>(leads)

  const toggleEstagio = (s: LeadStage) => {
    setPage(1)
    setEstagios((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }
  const toggleOrigem = (o: string) => {
    setPage(1)
    setOrigens((prev) => (prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]))
  }

  const destinatarios: Destinatario[] = selecao.selectedItems.map((l) => ({ id: l.id, name: l.name, phone: l.phone }))
  const temFiltro = estagios.length > 0 || origens.length > 0

  if (isLoading) {
    return (
      <div className="p-6">
        <SkeletonTable rows={8} />
      </div>
    )
  }
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar o CRM.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 flex flex-col gap-6 max-w-[1400px]">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">CRM</h1>
        <p className="text-sm text-gray-500">
          A fila da semana: quem precisa de resposta, quem sumiu, quem vale reativar.
        </p>
      </header>

      <ChipsDeEstagio
        contagem={contagem}
        selecionados={estagios}
        onToggle={toggleEstagio}
        mostrarMais={mostrarMais}
        onMostrarMais={() => setMostrarMais(true)}
      />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrar por origem">
        <span className="text-xs uppercase tracking-wide text-gray-400">Origem</span>
        {ORIGENS.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={origens.includes(o.value)}
            onClick={() => toggleOrigem(o.value)}
            className={[
              'rounded-md px-3 py-1.5 text-sm cursor-pointer min-h-11 transition-colors duration-150',
              origens.includes(o.value) ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100',
            ].join(' ')}
          >
            {o.label}
          </button>
        ))}
      </div>

      {selecao.selectedIds.size > 0 && (
        <div className="flex items-center justify-between rounded-xl bg-brand-50 px-4 py-3 text-sm">
          <span className="text-brand-800">
            {selecao.selectedIds.size} selecionado{selecao.selectedIds.size > 1 ? 's' : ''}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={selecao.clear}>
              Limpar
            </Button>
            {ehAdmin && (
              <Button size="sm" onClick={() => setDisparoAberto(true)}>
                Disparar mensagem
              </Button>
            )}
          </div>
        </div>
      )}

      {leads.length === 0 ? (
        <EmptyState
          title="Nada aqui"
          description={
            temFiltro
              ? 'Nenhum lead com esse filtro. Tire um chip para ampliar.'
              : 'Os estágios aparecem depois da primeira rodada noturna do classificador.'
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-4 py-3">
                  <input
                    type="checkbox"
                    aria-label="Selecionar todos da página"
                    checked={selecao.pageFullySelected}
                    onChange={selecao.togglePage}
                    className="h-4 w-4 cursor-pointer accent-brand-600"
                  />
                </th>
                <th className="px-3 py-3">Contato</th>
                <th className="px-3 py-3">Origem</th>
                <th className="px-3 py-3">Estágio</th>
                <th className="px-3 py-3">Última mensagem</th>
                <th className="px-3 py-3">Parado há</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {leads.map((lead) => (
                <Fragment key={lead.id}>
                  <tr className="hover:bg-gray-50/50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${lead.name ?? lead.phone}`}
                        checked={selecao.selectedIds.has(lead.id)}
                        onChange={() => selecao.toggle(lead)}
                        className="h-4 w-4 cursor-pointer accent-brand-600"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <p className="font-medium text-gray-800">{lead.name || 'Sem nome'}</p>
                      <p className="text-gray-500">{formatPhone(lead.phone)}</p>
                    </td>
                    <td className="px-3 py-3">
                      <Badge variant="neutral">{rotuloDaOrigem(lead.source)}</Badge>
                    </td>
                    <td className="px-3 py-3">
                      <EstagioBadge
                        lead={lead}
                        onCorrigir={() => setEditando(editando === lead.id ? null : lead.id)}
                      />
                    </td>
                    <td className="px-3 py-3 text-gray-600 whitespace-nowrap">{ultimaMensagem(lead)}</td>
                    <td className="px-3 py-3 text-gray-700 whitespace-nowrap tabular-nums">
                      {lead.dias_parado == null ? '-' : `${lead.dias_parado} d`}
                    </td>
                  </tr>
                  {editando === lead.id && (
                    <tr>
                      <td colSpan={6} className="px-4 pb-3">
                        <PopoverDeEstagio lead={lead} onFechar={() => setEditando(null)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
            onPerPageChange={(n) => {
              setPerPage(n)
              setPage(1)
            }}
          />
        </div>
      )}

      {disparoAberto && (
        <BatchMessageModal
          open
          patients={destinatarios}
          availableDates={availableDates}
          clinicTemplate={clinic?.batch_message_template}
          onClose={() => setDisparoAberto(false)}
          onDone={selecao.clear}
        />
      )}
    </div>
  )
}
