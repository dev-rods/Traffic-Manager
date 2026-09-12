import { useEffect, useMemo, useRef } from 'react'
import { useConversationMessages } from '@/hooks/useBot'
import { formatPhone } from '@/utils/formatPhone'
import { Button } from '@/components/ui/Button'
import type { MessageStatus, PauseReason } from '@/types'

interface ConversationThreadProps {
  phone: string
  senderName?: string
  botPaused?: boolean
  /** Por que o bot não responde: muda o texto do botão e explica o motivo. */
  pauseReason?: PauseReason
  /** O bot foi ativado sobre uma pergunta sem resposta e está escrevendo. */
  answering?: boolean
  onPause: () => void
  onResume: () => void
  onClose: () => void
  pauseLoading?: boolean
  resumeLoading?: boolean
}

/**
 * "Pausado" e "não elegível" parecem iguais na tela mas têm causas diferentes:
 * o primeiro alguém fez, o segundo é o padrão da clínica para quem não veio da
 * landing page. Sem distinguir, o botão prometia uma ação que não teria efeito.
 */
const MOTIVO_DA_PAUSA: Record<NonNullable<PauseReason>, string> = {
  attendant: 'Atendimento humano em andamento',
  clinic_paused: 'Bot desligado para toda a clínica',
  not_eligible: 'Fora da regra de resposta automática',
}

const READ_STATUSES: MessageStatus[] = ['READ', 'READ_BY_ME', 'PLAYED']
const DELIVERED_STATUSES: MessageStatus[] = ['RECEIVED']

/**
 * WhatsApp-style delivery indicator for outbound messages.
 * Mapping follows the user's mental model (not literal WhatsApp semantics):
 *   FAILED / SENT (no RECEIVED webhook yet) → "não entregue" (error glyph)
 *   RECEIVED                                → "entregue"    (single tick)
 *   READ / READ_BY_ME / PLAYED              → "lida"        (double ticks, bright)
 */
function DeliveryTicks({ status }: { status: MessageStatus }) {
  const isRead = READ_STATUSES.includes(status)
  const isDelivered = DELIVERED_STATUSES.includes(status)

  if (!isDelivered && !isRead) {
    return (
      <svg aria-label="Não entregue" className="w-3.5 h-3.5 text-red-300" viewBox="0 0 20 20" fill="currentColor">
        <title>Não entregue</title>
        <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm-.75 4h1.5v6h-1.5V6zm.75 9a1 1 0 110-2 1 1 0 010 2z" />
      </svg>
    )
  }

  const label = isRead ? 'Lida' : 'Entregue'
  const color = isRead ? 'text-white' : 'text-brand-200'

  return (
    <svg
      aria-label={label}
      className={['w-4 h-4', color].join(' ')}
      viewBox="0 0 20 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <title>{label}</title>
      {isRead && <path d="M2 7l3.5 3.5L12 4" />}
      <path d="M8 7l3.5 3.5L18 4" />
    </svg>
  )
}

export function ConversationThread({ phone, senderName, botPaused, pauseReason, answering, onPause, onResume, onClose, pauseLoading, resumeLoading }: ConversationThreadProps) {
  const { data, isLoading } = useConversationMessages(phone)
  const messages = useMemo(() => data?.messages ?? [], [data])
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages load or change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, answering])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 cursor-pointer">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <p className="text-sm font-semibold text-gray-800">{senderName || formatPhone(phone)}</p>
            <p className="text-xs text-gray-400">{formatPhone(phone)}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {botPaused && pauseReason && (
            <span className="text-xs text-gray-400">{MOTIVO_DA_PAUSA[pauseReason]}</span>
          )}
          {botPaused ? (
            <Button size="sm" onClick={onResume} loading={resumeLoading}>
              {pauseReason === 'not_eligible' ? 'Ativar bot' : 'Retomar bot'}
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={onPause} loading={pauseLoading}>Pausar bot</Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {isLoading ? (
          <div className="text-center py-8">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-gray-400 mt-2">Carregando mensagens...</p>
          </div>
        ) : messages.length === 0 ? (
          <p className="text-center text-sm text-gray-400 py-8">Nenhuma mensagem encontrada</p>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={[
                'max-w-[75%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-line',
                msg.direction === 'INBOUND'
                  ? 'bg-gray-100 text-gray-800 rounded-bl-sm'
                  : 'bg-brand-500 text-white ml-auto rounded-br-sm',
              ].join(' ')}
            >
              <p>{msg.content}</p>
              <div className={[
                'flex items-center gap-1 mt-1',
                msg.direction === 'OUTBOUND' ? 'justify-end' : '',
              ].join(' ')}>
                <p className={[
                  'text-[10px]',
                  msg.direction === 'INBOUND' ? 'text-gray-400' : 'text-brand-200',
                ].join(' ')}>
                  {msg.created_at ? new Date(msg.created_at).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : ''}
                </p>
                {msg.direction === 'OUTBOUND' && <DeliveryTicks status={msg.status} />}
              </div>
            </div>
          ))
        )}

        {/* A resposta leva alguns segundos: sem sinal, a tela parece inerte e
            quem clicou clica de novo. */}
        {answering && (
          <div className="ml-auto flex max-w-[75%] items-center gap-2 rounded-2xl rounded-br-sm bg-brand-50 px-3.5 py-2.5 text-sm text-brand-700">
            <span className="flex gap-1" aria-hidden="true">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400 motion-safe:animate-pulse" />
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400 motion-safe:animate-pulse [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400 motion-safe:animate-pulse [animation-delay:300ms]" />
            </span>
            Respondendo o que ficou em aberto
          </div>
        )}
      </div>
    </div>
  )
}
