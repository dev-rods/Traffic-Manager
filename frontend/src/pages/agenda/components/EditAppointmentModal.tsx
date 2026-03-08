import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUpdateAppointment } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { useServiceAreas } from '@/hooks/useAreas'
import type { Appointment, UpdateAppointmentPayload } from '@/types'

interface EditAppointmentModalProps {
  appointment: Appointment | null
  onClose: () => void
}

export function EditAppointmentModal({ appointment, onClose }: EditAppointmentModalProps) {
  const updateAppointment = useUpdateAppointment()
  const { data: services } = useServices()

  const initialAreaIds = appointment?.area_ids?.split(',') ?? []

  const [date, setDate] = useState(appointment?.appointment_date ?? '')
  const [time, setTime] = useState(appointment?.start_time.slice(0, 5) ?? '')
  const [notes, setNotes] = useState(appointment?.notes ?? '')
  const [serviceId, setServiceId] = useState(appointment?.service_id ?? '')
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>(initialAreaIds)
  const [prevServiceId, setPrevServiceId] = useState(serviceId)
  const [error, setError] = useState<string | null>(null)

  const { data: serviceAreas } = useServiceAreas(serviceId || undefined)

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    // Only reset if the user actually changed the service (not initial render)
    if (prevServiceId !== '') {
      setSelectedAreaIds([])
    }
  }

  if (!appointment) return null

  const a = appointment
  const displayName = a.patient_name || a.full_name || 'Sem nome'

  const dateChanged = date !== a.appointment_date
  const timeChanged = time !== a.start_time.slice(0, 5)
  const notesChanged = notes !== (a.notes ?? '')
  const serviceChanged = serviceId !== a.service_id
  const areasChanged = (() => {
    const sorted = [...selectedAreaIds].sort()
    const origSorted = [...initialAreaIds].sort()
    return sorted.length !== origSorted.length || sorted.some((v, i) => v !== origSorted[i])
  })()

  const hasChanges = dateChanged || timeChanged || notesChanged || serviceChanged || areasChanged

  const toggleArea = (areaId: string) => {
    setSelectedAreaIds((prev) =>
      prev.includes(areaId)
        ? prev.filter((id) => id !== areaId)
        : [...prev, areaId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!date || !time) {
      setError('Data e horário são obrigatórios.')
      return
    }

    if (!serviceId) {
      setError('Selecione um serviço.')
      return
    }

    if (!hasChanges) {
      onClose()
      return
    }

    setError(null)
    try {
      const payload: UpdateAppointmentPayload = {}

      if (dateChanged) payload.date = date
      if (timeChanged) payload.time = time
      if (notesChanged) payload.notes = notes

      if (serviceChanged || areasChanged) {
        payload.serviceId = serviceId
        if (selectedAreaIds.length > 0) {
          payload.serviceAreaPairs = selectedAreaIds.map((areaId) => ({
            serviceId,
            areaId,
          }))
        }
      }

      await updateAppointment.mutateAsync({
        appointmentId: a.id,
        payload,
      })
      onClose()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response: { data?: { message?: string } } }).response
        setError(response.data?.message ?? 'Erro ao atualizar agendamento')
      } else {
        setError('Erro ao atualizar agendamento')
      }
    }
  }

  return (
    <Modal open onClose={onClose} title="Editar agendamento">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {/* Patient info (read-only) */}
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-sm font-medium text-gray-800">{displayName}</p>
        </div>

        {/* Date + Time */}
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Data"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <Input
            label="Horário"
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </div>

        {/* Service */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Serviço</label>
          <select
            value={serviceId}
            onChange={(e) => setServiceId(e.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          >
            <option value="">Selecione...</option>
            {services?.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Areas */}
        {serviceId && serviceAreas && serviceAreas.length > 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">
              Áreas ({selectedAreaIds.length} selecionada{selectedAreaIds.length !== 1 ? 's' : ''})
            </label>
            <div className="rounded-lg border border-gray-200 divide-y divide-gray-100 max-h-40 overflow-y-auto">
              {serviceAreas.map((area) => (
                <label
                  key={area.area_id}
                  className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedAreaIds.includes(area.area_id)}
                      onChange={() => toggleArea(area.area_id)}
                      className="accent-brand-500"
                    />
                    <span className="text-sm text-gray-800">{area.name}</span>
                  </div>
                  {area.effective_price_cents > 0 && (
                    <span className="text-xs text-gray-400">
                      {(area.effective_price_cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </span>
                  )}
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Observações</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Observações sobre o agendamento..."
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
          />
        </div>

        {/* Reschedule warning */}
        {(dateChanged || timeChanged) && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-4 py-3">
            O agendamento será reagendado para <strong>{date}</strong> às <strong>{time}</strong>.
            Conflitos de horário serão verificados automaticamente.
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={updateAppointment.isPending || !hasChanges}
            className={[
              'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              updateAppointment.isPending || !hasChanges
                ? 'bg-brand-300 text-white cursor-not-allowed'
                : 'bg-brand-500 hover:bg-brand-600 text-white',
            ].join(' ')}
          >
            {updateAppointment.isPending ? 'Salvando...' : 'Salvar alterações'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
