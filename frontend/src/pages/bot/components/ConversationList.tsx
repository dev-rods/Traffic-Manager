import type { KeyboardEvent } from 'react'
import { formatPhone } from '@/utils/formatPhone'
import { Button } from '@/components/ui/Button'
import { CLASSE_DO_SELO, SELO_DA_PAUSA } from '@/lib/motivoDaPausa'
import type { ConversationPreview } from '@/types'

interface ConversationListProps {
  conversations: ConversationPreview[]
  selectedPhone: string | null
  onSelect: (phone: string, senderName: string) => void
  /** "Ativar bot" direto na linha, para quem está fora da regra (PRD 031). */
  onResume: (phone: string) => void
  /** Telefone cuja ativação está em andamento; só esse botão gira. */
  resumeLoadingPhone: string | null
  /** Texto do vazio: muda quando é um filtro que não achou ninguém. */
  emptyMessage?: string
}

/**
 * A lista das conversas recentes, com um selo dizendo por que o bot está
 * calado em cada uma. Antes a recepção abria uma a uma para descobrir quem
 * estava fora da regra; agora enxerga de cara e ativa o bot sem abrir.
 *
 * A linha não é um <button>: ela carrega outro botão dentro, e botão dentro de
 * botão é HTML inválido. Vira um elemento clicável com teclado.
 */
export function ConversationList({
  conversations,
  selectedPhone,
  onSelect,
  onResume,
  resumeLoadingPhone,
  emptyMessage = 'Nenhuma conversa recente',
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-gray-400">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-100">
      {conversations.map((conv) => {
        const abrir = () => onSelect(conv.phone, conv.sender_name)
        const aoTeclar = (e: KeyboardEvent<HTMLDivElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            abrir()
          }
        }
        const motivo = conv.pause_reason ?? null
        const nome = conv.sender_name || formatPhone(conv.phone)

        return (
          <div
            key={conv.phone}
            role="button"
            tabIndex={0}
            aria-label={`Abrir conversa com ${nome}`}
            onClick={abrir}
            onKeyDown={aoTeclar}
            className={[
              'w-full text-left px-4 py-3 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
              selectedPhone === conv.phone ? 'bg-brand-50' : 'hover:bg-gray-50',
            ].join(' ')}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{nome}</p>
                  {motivo ? (
                    <span
                      className={[
                        'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium',
                        CLASSE_DO_SELO[motivo],
                      ].join(' ')}
                    >
                      {SELO_DA_PAUSA[motivo]}
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-gray-400 truncate mt-0.5">
                  {conv.last_direction === 'OUTBOUND' && <span className="text-gray-300">Bot: </span>}
                  {conv.last_message}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1 flex-shrink-0">
                <span className="text-[10px] text-gray-300">
                  {conv.last_message_at
                    ? new Date(conv.last_message_at).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
                    : ''}
                </span>
                {motivo === 'not_eligible' ? (
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      onResume(conv.phone)
                    }}
                    loading={resumeLoadingPhone === conv.phone}
                  >
                    Ativar bot
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
