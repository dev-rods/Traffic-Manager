import type { Service } from '@/types'
import { Modal } from './ui/Modal'
import { Button } from './ui/Button'

interface CartAddedModalProps {
  open: boolean
  service: Service | null
  onClose: () => void
  onAddAnother: () => void
  onContinue: () => void
}

export function CartAddedModal({ open, service, onClose, onAddAnother, onContinue }: CartAddedModalProps) {
  if (!service) return null

  return (
    <Modal open={open} onClose={onClose} title="Serviço adicionado">
      <p className="mb-6 text-sm text-ink-600">
        <span className="font-medium text-ink-900">{service.name}</span> foi adicionado ao carrinho. O que
        você gostaria de fazer agora?
      </p>
      <div className="flex flex-col gap-2">
        <Button onClick={onContinue}>Continuar</Button>
        <Button variant="ghost" onClick={onAddAnother}>
          Adicionar outro serviço
        </Button>
      </div>
    </Modal>
  )
}
