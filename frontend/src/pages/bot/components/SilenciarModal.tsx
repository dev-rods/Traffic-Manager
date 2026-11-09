import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { formatPhone } from '@/utils/formatPhone'

interface SilenciarModalProps {
  open: boolean
  phone: string
  onClose: () => void
  onConfirm: (motivo: string) => void
  loading?: boolean
}

const MOTIVO_MIN = 3

/**
 * O motivo é obrigatório, e isso não é burocracia (PRD 039 §5): um número
 * calado sem explicação é o que ninguém sabe desfazer meses depois. Quem abre
 * esta conversa precisa ler por que o bot está quieto.
 */
export function SilenciarModal({ open, phone, onClose, onConfirm, loading }: SilenciarModalProps) {
  // O texto não precisa ser limpo à mão: quem abre passa `key={phone}`, e o
  // modal remonta vazio a cada contato.
  const [motivo, setMotivo] = useState('')

  const valido = motivo.trim().length >= MOTIVO_MIN

  return (
    <Modal open={open} onClose={onClose} title="Silenciar o bot para este contato">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          O bot deixa de responder <strong className="font-medium text-gray-800">{formatPhone(phone)}</strong>{' '}
          por tempo indeterminado. Só volta quando alguém clicar em "Reativar bot" - nenhum prazo
          traz ele de volta.
        </p>
        <p className="text-sm text-gray-600">
          O lembrete de sessão continua sendo enviado. Se a pessoa responder, a conversa fica
          esperando atendimento humano.
        </p>

        <div>
          <label htmlFor="motivo-do-silencio" className="text-xs font-medium text-gray-500 block mb-1.5">
            Por que silenciar? <span className="text-gray-300">(obrigatório)</span>
          </label>
          <textarea
            id="motivo-do-silencio"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder="Ex.: atendimento conduzido à mão pela recepção"
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => onConfirm(motivo.trim())} disabled={!valido} loading={loading}>
            Silenciar bot
          </Button>
        </div>
      </div>
    </Modal>
  )
}
