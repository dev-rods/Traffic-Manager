import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { useCancelAppointment } from '@/hooks/useAppointments'
import type { Appointment } from '@/types'

interface CancelAppointmentModalProps {
  appointment: Appointment | null
  onClose: () => void
}

export function CancelAppointmentModal({ appointment, onClose }: CancelAppointmentModalProps) {
  const cancelMutation = useCancelAppointment()
  const [error, setError] = useState<string | null>(null)

  const displayName = appointment?.patient_name || appointment?.full_name || 'Paciente sem nome'
  const timeSlot = appointment
    ? `${appointment.start_time.slice(0, 5)} – ${appointment.end_time.slice(0, 5)}`
    : ''

  const handleConfirm = async () => {
    if (!appointment) return
    setError(null)
    try {
      await cancelMutation.mutateAsync(appointment.id)
      onClose()
    } catch {
      setError('Erro ao cancelar agendamento. Tente novamente.')
    }
  }

  const handleClose = () => {
    setError(null)
    onClose()
  }

  return (
    <Modal open={!!appointment} onClose={handleClose} title="Cancelar agendamento">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Tem certeza que deseja cancelar o agendamento de{' '}
          <span className="font-semibold text-gray-800">{displayName}</span> às{' '}
          <span className="font-semibold text-gray-800">{timeSlot}</span>?
        </p>

        <p className="text-xs text-gray-400">
          Essa acao nao pode ser desfeita.
        </p>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
          >
            Voltar
          </button>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={cancelMutation.isPending}
            className={[
              'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              cancelMutation.isPending
                ? 'bg-red-300 text-white cursor-not-allowed'
                : 'bg-red-500 hover:bg-red-600 text-white',
            ].join(' ')}
          >
            {cancelMutation.isPending ? 'Cancelando...' : 'Confirmar cancelamento'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
