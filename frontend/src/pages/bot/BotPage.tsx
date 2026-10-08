import { useState } from 'react'
import { useClinic, useUpdateClinic } from '@/hooks/useClinic'
import { useActiveConversations, useRecentConversations, useBotMetrics, usePauseBot, useResumeBot, useFecharTarefa, ESPERA_RESPOSTA_RETOMADA_MS } from '@/hooks/useBot'
import { SkeletonTable, SkeletonCard } from '@/components/ui/Skeleton'
import { Switch } from '@/components/ui/Switch'
import { Card } from '@/components/ui/Card'
import { ConversationList } from './components/ConversationList'
import { FilaDeAtendimento } from './components/FilaDeAtendimento'
import { ConversationThread } from './components/ConversationThread'

type MetricsPeriod = 'today' | 'week' | 'month'

export function BotPage() {
  const { data: clinic, isLoading: clinicLoading } = useClinic()
  const updateClinic = useUpdateClinic()
  const [period, setPeriod] = useState<MetricsPeriod>('today')
  const { data: metrics, isLoading: metricsLoading } = useBotMetrics(period)
  const {
    data: activeData,
    isLoading: activeLoading,
    isError: activeError,
    refetch: recarregarFila,
  } = useActiveConversations()
  const { data: recentData, isLoading: recentLoading } = useRecentConversations()
  const pauseBot = usePauseBot()
  const resumeBot = useResumeBot()
  const fecharTarefa = useFecharTarefa()

  const [selectedPhone, setSelectedPhone] = useState<string | null>(null)
  const [selectedName, setSelectedName] = useState('')
  // Telefone que o bot está respondendo agora. Guardar o telefone, e não um
  // booleano, evita mostrar o indicador na conversa errada se o usuário trocar
  // de conversa enquanto a resposta é escrita.
  const [answeringPhone, setAnsweringPhone] = useState<string | null>(null)

  // A conversa selecionada carrega o motivo da pausa; sem ela o botão não sabe
  // se deve dizer "Retomar" (alguém pausou) ou "Ativar" (nunca foi elegível).
  const selectedConversation = (activeData?.conversations ?? []).find((c) => c.phone === selectedPhone)

  const handleToggleBotGlobal = async (active: boolean) => {
    await updateClinic.mutateAsync({ bot_paused: !active })
  }

  const botActive = !clinic?.bot_paused

  if (clinicLoading) return <div className="p-6"><SkeletonTable rows={6} /></div>

  return (
    <div className="p-6 space-y-8">
      {/* Header + Global Control */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Bot do WhatsApp</h1>
          <p className="text-sm text-gray-400 mt-1">Gerencie o bot, veja conversas e métricas</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={['text-sm font-medium', botActive ? 'text-emerald-600' : 'text-red-500'].join(' ')}>
            {botActive ? 'Bot ativo' : 'Bot pausado'}
          </span>
          <Switch
            checked={botActive}
            onChange={(v) => void handleToggleBotGlobal(v)}
            label="Bot ativo"
          />
        </div>
      </div>

      {/* Metrics */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-800">Métricas</h2>
          <div className="flex gap-1">
            {(['today', 'week', 'month'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={[
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer',
                  period === p ? 'bg-brand-500 text-white' : 'text-gray-500 hover:bg-gray-100',
                ].join(' ')}
              >
                {p === 'today' ? 'Hoje' : p === 'week' ? 'Semana' : 'Mês'}
              </button>
            ))}
          </div>
        </div>
        {metricsLoading ? (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : metrics ? (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Conversas" value={metrics.total_conversations} />
            <MetricCard label="Mensagens enviadas" value={metrics.messages_sent} />
            <MetricCard label="Taxa de conversão" value={`${metrics.conversion_rate}%`} />
            <MetricCard label="Handoffs" value={metrics.handoff_count} />
          </div>
        ) : null}
      </section>

      {/*
        A fila de quem precisa de uma pessoa.
        Fica ACIMA das conversas recentes de propósito: é a única parte desta
        tela que representa trabalho pendente, e trabalho pendente não espera o
        scroll. A lista anterior ficava escondida quando vazia; esta não, porque
        a recepção precisa saber que olhou e não havia ninguém - ausência de
        seção não é a mesma informação que "ninguém esperando".
      */}
      <FilaDeAtendimento
        conversations={activeData?.conversations ?? []}
        isLoading={activeLoading}
        isError={activeError}
        onRetry={() => void recarregarFila()}
        onSelect={(phone, nome) => { setSelectedPhone(phone); setSelectedName(nome) }}
        onResume={(phone) => resumeBot.mutate(phone)}
        resumeLoading={resumeBot.isPending}
        onFecharTarefa={(tarefaId) => fecharTarefa.mutate(tarefaId)}
        fecharLoading={fecharTarefa.isPending}
      />

      {/* Conversations */}
      <section>
        <h2 className="text-sm font-semibold text-gray-800 mb-3">Conversas recentes</h2>
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden h-[calc(100vh-280px)] min-h-96">
          <div className="flex h-full">
            {/* Conversation list */}
            <div className={[
              'border-r border-gray-200 overflow-y-auto h-full',
              selectedPhone ? 'w-80 flex-shrink-0' : 'flex-1',
            ].join(' ')}>
              {recentLoading || activeLoading ? (
                <div className="p-4"><SkeletonTable rows={5} /></div>
              ) : (
                <ConversationList
                  conversations={recentData?.conversations ?? []}
                  selectedPhone={selectedPhone}
                  onSelect={(phone, name) => { setSelectedPhone(phone); setSelectedName(name) }}
                />
              )}
            </div>

            {/* Thread panel */}
            {selectedPhone && (
              <div className="flex-1 h-full overflow-hidden">
                <ConversationThread
                  phone={selectedPhone}
                  senderName={selectedName}
                  botPaused={selectedConversation?.bot_paused ?? false}
                  pauseReason={selectedConversation?.pause_reason ?? null}
                  onPause={() => pauseBot.mutate(selectedPhone)}
                  answering={answeringPhone === selectedPhone}
                  onResume={() => {
                    const phone = selectedPhone
                    resumeBot.mutate(phone, {
                      onSuccess: (data) => {
                        if (!data.answering_open_question) return
                        setAnsweringPhone(phone)
                        window.setTimeout(
                          () => setAnsweringPhone((atual) => (atual === phone ? null : atual)),
                          ESPERA_RESPOSTA_RETOMADA_MS,
                        )
                      },
                    })
                  }}
                  onClose={() => setSelectedPhone(null)}
                  pauseLoading={pauseBot.isPending}
                  resumeLoading={resumeBot.isPending}
                />
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs text-gray-400 font-medium">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </Card>
  )
}
