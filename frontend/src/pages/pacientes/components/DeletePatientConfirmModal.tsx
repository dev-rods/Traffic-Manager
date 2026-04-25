import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useDeletePatient } from '@/hooks/usePatients'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface DeletePatientConfirmModalProps {
  patient: PatientWithStats | null
  onClose: () => void
  onSuccess: (patientName: string) => void
}

export function DeletePatientConfirmModal({
  patient,
  onClose,
  onSuccess,
}: DeletePatientConfirmModalProps) {
  const mutation = useDeletePatient()

  if (!patient) return null

  const handleDelete = async () => {
    try {
      await mutation.mutateAsync(patient.id)
      onSuccess(patient.name ?? 'Paciente')
      mutation.reset()
      onClose()
    } catch {
      // erro renderizado inline via mutation.isError
    }
  }

  const handleClose = () => {
    if (mutation.isPending) return
    mutation.reset()
    onClose()
  }

  return (
    <Modal open onClose={handleClose} title="Excluir paciente">
      <div className="space-y-4">
        <p className="text-sm text-gray-700">
          Tem certeza que deseja excluir{' '}
          <strong className="text-gray-900">{patient.name ?? 'este paciente'}</strong>{' '}
          <span className="text-gray-500">({formatPhone(patient.phone)})</span>?
        </p>
        <p className="text-xs text-gray-500 leading-relaxed">
          O paciente sai da lista, mas o histórico de agendamentos é preservado. Se ele voltar a
          entrar em contato pelo WhatsApp ou for cadastrado novamente, será restaurado
          automaticamente.
        </p>
        {mutation.isError && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            Falha ao excluir. Tente novamente.
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={handleClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button variant="danger" onClick={() => void handleDelete()} loading={mutation.isPending}>
            Excluir paciente
          </Button>
        </div>
      </div>
    </Modal>
  )
}
