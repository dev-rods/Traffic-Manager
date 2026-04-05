import { useEffect, useMemo, useRef } from 'react'
import { useConversationMessages } from '@/hooks/useBot'
import { formatPhone } from '@/utils/formatPhone'
import { Button } from '@/components/ui/Button'

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
              <p className={[
                'text-[10px] mt-1',
                msg.direction === 'INBOUND' ? 'text-gray-400' : 'text-brand-200',
              ].join(' ')}>
                {msg.created_at ? new Date(msg.created_at).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : ''}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
