import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useCancelAppointment } from '@/hooks/useAppointments'
import { desfechoDe, type Desfecho } from '@/lib/desfecho'
import { DesfechoField } from './DesfechoField'
import type { Appointment, AvailabilityRule } from '@/types'

interface CancelAppointmentModalProps {
  appointment: Appointment | null
  onClose: () => void
  /** A pessoa vai remarcar: editar a data mantém o mesmo registro (PRD 035). */
  onReschedule: (appointment: Appointment) => void
  /** Regras de horário, para antecipar o desfecho (PRD 054). Sem elas, vale a hora da sessão. */
  regras?: AvailabilityRule[]
}

export function CancelAppointmentModal({ appointment, onClose, onReschedule, regras }: CancelAppointmentModalProps) {
  const cancelMutation = useCancelAppointment()
  const [error, setError] = useState<string | null>(null)
  // O desfecho automático pela antecedência (PRD 054) e a escolha da recepção.
  const automatico: Desfecho = appointment ? desfechoDe(regras, appointment) : 'CANCELLED'
  const [desfecho, setDesfecho] = useState<Desfecho | null>(null)
  const [motivo, setMotivo] = useState('')
  const escolhido = desfecho ?? automatico
  const diverge = escolhido !== automatico
  const motivoFalta = diverge && !motivo.trim()

  const displayName = appointment?.patient_name || appointment?.full_name || 'Paciente sem nome'
  const timeSlot = appointment
    ? `${appointment.start_time.slice(0, 5)} – ${appointment.end_time.slice(0, 5)}`
    : ''

  const handleConfirm = async () => {
    if (!appointment || motivoFalta) return
    setError(null)
    try {
      await cancelMutation.mutateAsync({
        appointmentId: appointment.id,
        ...(diverge ? { outcome: escolhido, outcomeReason: motivo.trim() } : {}),
      })
      handleClose()
    } catch {
      setError('Erro ao cancelar agendamento. Tente novamente.')
    }
  }

  const handleClose = () => {
    setError(null)
    setDesfecho(null)
    setMotivo('')
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

        <DesfechoField
          automatico={automatico}
          valor={escolhido}
          onChange={setDesfecho}
          motivo={motivo}
          onMotivo={setMotivo}
        />

        <p className="text-xs text-gray-400">
          Essa acao nao pode ser desfeita.
        </p>

        {/* Um terço dos cancelamentos eram remarcações feitas como cancelar +
            criar (PRD 035). O caminho certo fica aqui, onde a mão já está. */}
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 space-y-2">
          <p>A pessoa vai remarcar? Então não cancele: edite a data e o agendamento continua o mesmo.</p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { if (appointment) onReschedule(appointment) }}
          >
            Remarcar em vez de cancelar
          </Button>
        </div>

        {/* Pago pelo iPad: cancelar não devolve o dinheiro (PRD 028, M7). */}
        {appointment?.payment_status === 'PAID' && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Este agendamento já foi pago. Cancelar não devolve o dinheiro: depois, faça o estorno
            em <span className="font-semibold">Relatórios → Caixa → Estornos pendentes</span>.
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={handleClose}>Voltar</Button>
          <Button
            variant="danger"
            onClick={() => void handleConfirm()}
            loading={cancelMutation.isPending}
            disabled={motivoFalta}
          >
            {escolhido === 'NO_SHOW' ? 'Registrar falta' : 'Confirmar cancelamento'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
