import { formatPhone } from '@/utils/formatPhone'
import type { ConversationPreview } from '@/types'

interface ConversationListProps {
  conversations: ConversationPreview[]
  selectedPhone: string | null
  onSelect: (phone: string, senderName: string) => void
}

export function ConversationList({ conversations, selectedPhone, onSelect }: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-gray-400">Nenhuma conversa recente</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-100">
      {conversations.map((conv) => (
        <button
          key={conv.phone}
          onClick={() => onSelect(conv.phone, conv.sender_name)}
          className={[
            'w-full text-left px-4 py-3 transition-colors cursor-pointer',
            selectedPhone === conv.phone ? 'bg-brand-50' : 'hover:bg-gray-50',
          ].join(' ')}
        >
          <div className="flex items-center justify-between">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-800 truncate">
                {conv.sender_name || formatPhone(conv.phone)}
              </p>
              <p className="text-xs text-gray-400 truncate mt-0.5">
                {conv.last_direction === 'OUTBOUND' && <span className="text-gray-300">Bot: </span>}
                {conv.last_message}
              </p>
            </div>
            <span className="text-[10px] text-gray-300 flex-shrink-0 ml-2">
              {conv.last_message_at
                ? new Date(conv.last_message_at).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
                : ''}
            </span>
          </div>
        </button>
      ))}
    </div>
  )
}
