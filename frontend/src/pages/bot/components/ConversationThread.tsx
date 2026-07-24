import { useEffect, useMemo, useRef, useState } from 'react'
import { useConversationMessages } from '@/hooks/useBot'
import { formatPhone } from '@/utils/formatPhone'
import { Button } from '@/components/ui/Button'
import type { MessageStatus } from '@/types'

interface ConversationThreadProps {
  phone: string
  senderName?: string
  botPaused?: boolean
  onPause: () => void
  onResume: () => void
  onClose: () => void
  pauseLoading?: boolean
  resumeLoading?: boolean
}

const READ_STATUSES: MessageStatus[] = ['READ', 'READ_BY_ME', 'PLAYED']
const DELIVERED_STATUSES: MessageStatus[] = ['RECEIVED', ...READ_STATUSES]
// If a message sits in SENT (accepted by z-api but no RECEIVED webhook) longer than this,
// WhatsApp almost certainly won't deliver it — treat as "sem confirmação" in the UI.
const STALE_SENT_THRESHOLD_MS = 2 * 60 * 1000

/**
 * WhatsApp-style delivery ticks for outbound messages, with one product-specific twist:
 * "SENT" older than 2 minutes escalates to a warning glyph, because at that point
 * WhatsApp is very unlikely to deliver and 1-tick would be misleading in the history.
 */
function DeliveryTicks({ status, createdAt, nowMs }: { status: MessageStatus; createdAt: string; nowMs: number }) {
  if (status === 'FAILED') {
    return (
      <svg aria-label="Falhou" className="w-3.5 h-3.5 text-red-300" viewBox="0 0 20 20" fill="currentColor">
        <title>Falhou</title>
        <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm-.75 4h1.5v6h-1.5V6zm.75 9a1 1 0 110-2 1 1 0 010 2z" />
      </svg>
    )
  }

  const isRead = READ_STATUSES.includes(status)
  const isDelivered = DELIVERED_STATUSES.includes(status)

  if (!isDelivered && status === 'SENT') {
    const sentAt = createdAt ? new Date(createdAt).getTime() : 0
    const isStale = sentAt > 0 && nowMs - sentAt > STALE_SENT_THRESHOLD_MS
    if (isStale) {
      return (
        <svg aria-label="Sem confirmação de entrega" className="w-3.5 h-3.5 text-amber-300" viewBox="0 0 20 20" fill="currentColor">
          <title>Sem confirmação de entrega</title>
          <path d="M9.1 2.6a1 1 0 011.8 0l7.5 13.5A1 1 0 0117.5 18h-15a1 1 0 01-.9-1.5L9.1 2.6zM10 8v4a.75.75 0 001.5 0V8A.75.75 0 0010 8zm0 6.5a1 1 0 100 2 1 1 0 000-2z" />
        </svg>
      )
    }
  }

  const color = isRead ? 'text-white' : 'text-brand-200'
  const label = isRead ? 'Lida' : isDelivered ? 'Entregue' : status === 'SENT' ? 'Enviada' : 'Aguardando'

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
      {isDelivered && <path d="M2 7l3.5 3.5L12 4" />}
      <path d="M8 7l3.5 3.5L18 4" />
    </svg>
  )
}

export function ConversationThread({ phone, senderName, botPaused, onPause, onResume, onClose, pauseLoading, resumeLoading }: ConversationThreadProps) {
  const { data, isLoading } = useConversationMessages(phone)
  const messages = useMemo(() => data?.messages ?? [], [data])
  const scrollRef = useRef<HTMLDivElement>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())

  // Auto-scroll to bottom when messages load or change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Refresh the "now" reference every 30s so the SENT → "sem confirmação" transition
  // shows up while the user is looking at the screen without needing a manual reload.
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])

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
        <div>
          {botPaused ? (
            <Button size="sm" onClick={onResume} loading={resumeLoading}>Retomar bot</Button>
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
                {msg.direction === 'OUTBOUND' && <DeliveryTicks status={msg.status} createdAt={msg.created_at} nowMs={nowMs} />}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
