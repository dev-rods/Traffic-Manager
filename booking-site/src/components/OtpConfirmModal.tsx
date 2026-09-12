import { Modal } from './ui/Modal'
import { OtpCodeForm } from './OtpCodeForm'

interface OtpConfirmModalProps {
  open: boolean
  clinicId: string
  phone: string
  onClose: () => void
  onVerified: (token: string) => void
}

export function OtpConfirmModal({ open, clinicId, phone, onClose, onVerified }: OtpConfirmModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Confirme o seu número">
      {open ? <OtpCodeForm clinicId={clinicId} phone={phone} onVerified={onVerified} /> : null}
    </Modal>
  )
}
