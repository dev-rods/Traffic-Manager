import { useEffect, useMemo, useRef } from 'react'
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

/**
 * WhatsApp-style delivery ticks for outbound messages.
 * - failed: red exclamation
 * - queued / sent: single tick (light)
 * - received: double ticks (light)
 * - read / played: double ticks (bright white) — mimics WhatsApp's blue read receipt
 *   but rendered in white here since the bubble background is already brand blue.
 */
function DeliveryTicks({ status }: { status: MessageStatus }) {
  if (status === 'FAILED') {
    return (
      <svg aria-label="Falhou" className="w-3.5 h-3.5 text-red-300" viewBox="0 0 20 20" fill="currentColor">
        <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm-.75 4h1.5v6h-1.5V6zm.75 9a1 1 0 110-2 1 1 0 010 2z" />
      </svg>
    )
  }

  const isRead = READ_STATUSES.includes(status)
  const isDelivered = DELIVERED_STATUSES.includes(status)
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
      {/* Back tick (rendered when delivered, i.e. two ticks) */}
      {isDelivered && <path d="M2 7l3.5 3.5L12 4" />}
      {/* Front tick (always rendered) */}
      <path d="M8 7l3.5 3.5L18 4" />
    </svg>
  )
}

export function ConversationThread({ phone, senderName, botPaused, onPause, onResume, onClose, pauseLoading, resumeLoading }: ConversationThreadProps) {
  const { data, isLoading } = useConversationMessages(phone)
  const messages = useMemo(() => data?.messages ?? [], [data])
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages load or change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

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
                {msg.direction === 'OUTBOUND' && <DeliveryTicks status={msg.status} />}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
