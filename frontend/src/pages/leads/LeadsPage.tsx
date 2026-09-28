import { useState } from 'react'
import { useAcoesDoLead, useLeads } from '@/hooks/useLeads'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { formatPhone } from '@/utils/formatPhone'
import type { Lead } from '@/types'
import type { ConversionsSummary } from '@/services/leads.service'

type FilterStatus = 'all' | 'booked' | 'not_booked'

export function LeadsPage() {
  const [status, setStatus] = useState<FilterStatus>('all')
  const bookedParam = status === 'all' ? undefined : status === 'booked'

  const { data, isLoading, isError, error, refetch } = useLeads({
    booked: bookedParam,
    // Quem chega direto no WhatsApp nao e lead captado: a tela mede o que o
    // site trouxe. Exclusao por origem, e no servidor - o LIMIT corta no banco,
    // entao filtrar aqui esconderia leads do site ao passar de 100.
    excludeSource: 'whatsapp',
    limit: 100,
  })

  const leads = data?.leads ?? []
  // Os totais vêm contados do banco. Eram calculados aqui sobre a página
  // carregada, enquanto "Total de leads" vinha do servidor: a taxa saía de uma
  // divisão entre numerador da página e denominador do conjunto, e era
  // exatamente o número usado para julgar a campanha.
  const totalLeads = data?.totals.total ?? 0
  const bookedCount = data?.totals.convertidos ?? 0
  const notBookedCount = data?.totals.nao_convertidos ?? 0
  const conversionRate = totalLeads > 0 ? Math.round((bookedCount / totalLeads) * 100) : 0
  const conversoes = data?.conversions ?? null

  if (isLoading) return <div className="p-6"><SkeletonTable rows={8} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar leads.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Leads</h1>
        <p className="text-sm text-gray-400 mt-1">
          Contatos capturados pelo site
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Total de leads" value={totalLeads} />
        <KpiCard label="Convertidos" value={bookedCount} />
        <KpiCard label="Não convertidos" value={notBookedCount} />
        <KpiCard label="Taxa de conversão" value={`${conversionRate}%`} />
      </div>

      {conversoes && <EnvioParaOGoogle resumo={conversoes} />}

      {/* Filter */}
      <div className="flex gap-1">
        {([
          { key: 'all' as const, label: 'Todos' },
          { key: 'booked' as const, label: 'Convertidos' },
          { key: 'not_booked' as const, label: 'Não convertidos' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setStatus(key)}
            className={[
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer',
              status === key ? 'bg-brand-500 text-white' : 'text-gray-500 hover:bg-gray-100',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      {leads.length === 0 ? (
        <EmptyState
          title="Nenhum lead encontrado"
          description={status !== 'all' ? 'Tente mudar o filtro.' : 'Leads aparecem quando alguém preenche o formulário da landing page ou chama no WhatsApp.'}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-5 py-3">Contato</th>
                <th className="px-3 py-3">Telefone</th>
                <th className="px-3 py-3">Fonte</th>
                <th className="px-3 py-3">Conversa</th>
                <th className="px-3 py-3">Atendimento</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Conversa inicial</th>
                <th className="px-3 py-3">Google</th>
                <th className="px-3 py-3">Valor 1o agend.</th>
                <th className="px-3 py-3">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {leads.map((lead: Lead) => (
                <tr key={lead.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800">{lead.name || 'Sem nome'}</p>
                  </td>
                  <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                    {formatPhone(lead.phone)}
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant="neutral">{lead.source}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <ConversationBadge lead={lead} />
                  </td>
                  <td className="px-3 py-3">
                    <AtendimentoBadge lead={lead} />
                  </td>
                  <td className="px-3 py-3">
                    <AcoesDeInicio lead={lead} />
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={lead.booked ? 'success' : 'warning'}>
                      {lead.booked ? 'Convertido' : 'Pendente'}
                    </Badge>
                  </td>
                  <td className="px-3 py-3">
                    <EnvioBadge lead={lead} />
                  </td>
                  <td className="px-3 py-3 text-gray-700 whitespace-nowrap">
                    {lead.first_appointment_value
                      ? `R$ ${lead.first_appointment_value.toFixed(2).replace('.', ',')}`
                      : '-'}
                  </td>
                  <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                    {new Date(lead.created_at).toLocaleDateString('pt-BR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/**
 * Estado da conversa do lead.
 *
 * A ordem das checagens importa: quem respondeu já foi contatado, então
 * "Respondeu" tem precedência sobre "Contatado".
 *
 * `has_whatsapp_chat` entra por último e é o que fecha o buraco que gerou esta
 * coluna: existe conversa no WhatsApp que nunca passou pelo bot, porque a
 * atendente respondeu pelo celular. Na Essência eram 17 de 37 leads do site
 * marcados como "Sem contato" tendo conversa desenvolvida.
 *
 * Não vira "Respondeu": a lista de chats do z-api não diz quem falou, e usá-la
 * para isso inflaria a taxa de conversão com conversas em que só a clínica
 * falou.
 */
function ConversationBadge({ lead }: { lead: Lead }) {
  if (lead.conversation_started_at) return <Badge variant="success">Respondeu</Badge>
  if (lead.first_contact_status === 'SENT') return <Badge variant="neutral">Contatado</Badge>
  if (lead.first_contact_status === 'QUEUED') return <Badge variant="warning">Na fila</Badge>
  if (lead.first_contact_status === 'FAILED') return <Badge variant="danger">Falhou</Badge>
  if (lead.has_whatsapp_chat) return <Badge variant="neutral">Tem conversa</Badge>
  return <Badge variant="neutral">Sem contato</Badge>
}

/** Quem está conduzindo a conversa agora. */
function AtendimentoBadge({ lead }: { lead: Lead }) {
  switch (lead.conversation_status) {
    case 'HUMANO':
      return <Badge variant="warning">Atendente</Badge>
    case 'AGUARDA_HUMANO':
      return <Badge variant="danger">Aguarda atendente</Badge>
    case 'BOT':
      return <Badge variant="success">Bot</Badge>
    default:
      return <span className="text-gray-300">-</span>
  }
}

/**
 * Os dois botoes de inicio de conversa.
 *
 * "Iniciar pelo Bot" so acende quando o servidor disse que pode. A regra tem
 * seis condicoes e vive em `elegibilidade_do_bot.py`; aqui so se renderiza o
 * que veio pronto, senao a mesma regra existiria em dois lugares e divergiria
 * em silencio.
 *
 * "Ja iniciada" alterna. Ele existe porque a API NAO enxerga o que ele
 * registra: quando a atendente escreve para quem nunca respondeu, a mensagem
 * chega ao webhook como LID sem telefone e se perde. Quem sabe e ela.
 */
function AcoesDeInicio({ lead }: { lead: Lead }) {
  const { iniciarPeloBot, alternarContatoManual } = useAcoesDoLead()
  const origem = lead.contact_started_source

  // Iniciada pelo bot tem estado proprio: mostra se saiu ou se esta na fila.
  if (origem === 'BOT') {
    return (
      <div className="flex flex-col gap-0.5">
        <Badge variant="success">Iniciada pelo bot</Badge>
        <span className="text-[11px] text-gray-400">
          {lead.first_contact_status === 'QUEUED' ? 'na fila' : 'enviada'}
        </span>
      </div>
    )
  }

  // Ja sabemos que comecou. Nao ha o que a atendente confirmar aqui, e pedir o
  // clique treinaria ela a clicar sem ler - justo no botao cuja unica razao de
  // existir e o caso em que ela sabe algo que a API nao mostra.
  if (origem === 'RESPONDEU' || origem === 'WHATSAPP') {
    return (
      <span title={lead.contact_started_message ?? ''}>
        <Badge variant="neutral">Já iniciada</Badge>
      </span>
    )
  }

  // Marcada por uma pessoa: e a unica que se desfaz, porque o clique dela e o
  // unico fato que um clique pode reverter.
  if (origem === 'HUMANO') {
    return (
      <Button
        size="sm"
        variant="success"
        disabled={alternarContatoManual.isPending || !lead.can_unmark_contact}
        loading={alternarContatoManual.isPending}
        title="Marcado por uma atendente. Clique para desmarcar."
        onClick={() => alternarContatoManual.mutate(lead.id)}
      >
        Já iniciada ✓
      </Button>
    )
  }

  // Ponto cego: nenhuma evidencia de contato. Aqui, e so aqui, a atendente
  // decide - ou manda o bot abrir, ou registra que ela mesma ja falou.
  return (
    <div className="flex items-center gap-1.5">
      <Button
        size="sm"
        variant="primary"
        disabled={!lead.can_start_bot || iniciarPeloBot.isPending}
        loading={iniciarPeloBot.isPending}
        title={lead.can_start_bot ? 'O bot abre a conversa agora' : lead.bot_block_message ?? ''}
        onClick={() => iniciarPeloBot.mutate(lead.id)}
      >
        Iniciar pelo Bot
      </Button>
      <Button
        size="sm"
        variant="secondary"
        disabled={alternarContatoManual.isPending}
        loading={alternarContatoManual.isPending}
        title="Registrar que você já falou com esta pessoa fora do bot"
        onClick={() => alternarContatoManual.mutate(lead.id)}
      >
        Já iniciada
      </Button>
    </div>
  )
}

/** Centavos em reais, sem casas quando são redondos: R$ 5.446 e não R$ 5.446,00. */
function emReais(cents: number) {
  return (cents / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
  })
}

/**
 * O que o Google Ads recebeu, e o que ainda não.
 *
 * Existe porque "Convertido" na tabela acima responde outra pergunta - se a
 * pessoa agendou. Se o Google soube disso é uma segunda camada, e o vão entre
 * as duas ficou invisível por semanas: 24 leads convertidos, zero enviados.
 *
 * Não é um card: são cards demais nesta tela, e aninhar mais um dentro da
 * mesma faixa dos KPIs roubaria hierarquia do que importa. Uma régua fina e
 * tipografia bastam para separar.
 */
function EnvioParaOGoogle({ resumo }: { resumo: ConversionsSummary }) {
  const nadaSubiu = resumo.enviadas === 0 && resumo.aguardando > 0

  return (
    <section
      aria-label="Envio de conversões ao Google Ads"
      className="border-t border-gray-100 pt-4"
    >
      <div className="flex flex-wrap items-baseline gap-x-8 gap-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-gray-400">
          Google Ads
        </h2>

        <Numero
          label="Enviadas"
          valor={resumo.enviadas}
          detalhe={resumo.enviadas > 0 ? emReais(resumo.enviadas_cents) : undefined}
        />
        <Numero
          label="Aguardando envio"
          valor={resumo.aguardando}
          detalhe={resumo.aguardando > 0 ? emReais(resumo.aguardando_cents) : undefined}
          destaque={nadaSubiu}
        />
        {resumo.retratadas > 0 && (
          <Numero label="Retratadas" valor={resumo.retratadas} />
        )}

        <p className="text-xs text-gray-400 ml-auto">
          {resumo.ultimo_envio
            ? `Último envio em ${new Date(resumo.ultimo_envio).toLocaleDateString('pt-BR')}`
            : 'Nenhum envio ainda'}
        </p>
      </div>

      {nadaSubiu && (
        <p className="mt-2 text-xs text-amber-700">
          {resumo.aguardando} agendamento{resumo.aguardando > 1 ? 's' : ''} de anúncio
          {resumo.aguardando > 1 ? ' estão' : ' está'} registrado
          {resumo.aguardando > 1 ? 's' : ''} aqui e o Google ainda não recebeu.
          O envio roda toda segunda.
        </p>
      )}
    </section>
  )
}

function Numero({
  label,
  valor,
  detalhe,
  destaque = false,
}: {
  label: string
  valor: number
  detalhe?: string
  destaque?: boolean
}) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="flex items-baseline gap-2">
        <span
          className={[
            'text-xl font-semibold tabular-nums',
            destaque ? 'text-amber-700' : 'text-gray-900',
          ].join(' ')}
        >
          {valor}
        </span>
        {detalhe && <span className="text-xs text-gray-500 tabular-nums">{detalhe}</span>}
      </p>
    </div>
  )
}

/** Rótulos da coluna "Google". Ausência não vira badge: não há o que enviar. */
const ENVIO_AO_GOOGLE = {
  ENVIADO: { label: 'Enviado', variant: 'success' as const },
  AGUARDANDO: { label: 'A enviar', variant: 'warning' as const },
  RETRATADO: { label: 'Retratado', variant: 'neutral' as const },
}

function EnvioBadge({ lead }: { lead: Lead }) {
  if (!lead.conversion_status) {
    return <span className="text-gray-300">-</span>
  }
  const { label, variant } = ENVIO_AO_GOOGLE[lead.conversion_status]
  return <Badge variant={variant}>{label}</Badge>
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs text-gray-400 font-medium">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </Card>
  )
}
