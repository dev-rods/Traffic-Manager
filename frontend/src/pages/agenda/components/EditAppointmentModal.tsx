import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { useUpdateAppointment } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { useServiceAreas } from '@/hooks/useAreas'
import { useAvailableSlots } from '@/hooks/useAvailabilityRules'
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

  // Discount state
  const initDiscountMode = appointment?.discount_reason === 'partnership'
    ? 'partnership' as const
    : appointment?.discount_reason === 'custom'
      ? 'custom' as const
      : appointment?.discount_pct && appointment.discount_pct > 0
        ? 'custom' as const
        : 'none' as const
  const [discountMode, setDiscountMode] = useState<'none' | 'partnership' | 'custom'>(initDiscountMode)
  const [customDiscountPct, setCustomDiscountPct] = useState(
    initDiscountMode === 'custom' && appointment?.discount_pct
      ? String(appointment.discount_pct)
      : ''
  )

  const { data: serviceAreas } = useServiceAreas(serviceId || undefined)

  // Compute total duration from selected areas for accurate slot calculation
  const totalDuration = selectedAreaIds.length > 0 && serviceAreas
    ? serviceAreas
        .filter((a) => selectedAreaIds.includes(a.area_id))
        .reduce((sum, a) => sum + a.effective_duration_minutes, 0)
    : undefined

  // Fetch available slots
  const { data: slotsData, isLoading: slotsLoading } = useAvailableSlots(
    date || undefined,
    serviceId || undefined,
    totalDuration,
  )
  const slots = slotsData?.slots ?? []

  // Include the current appointment's time in the slot list (it's "available" for itself)
  const currentSlot = appointment?.start_time.slice(0, 5) ?? ''
  const slotsWithCurrent = slots.includes(currentSlot)
    ? slots
    : currentSlot && date === appointment?.appointment_date
      ? [currentSlot, ...slots].sort()
      : slots

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    if (prevServiceId !== '') {
      setSelectedAreaIds([])
    }
  }

  // Clear selected time when date, service, or areas change (derived state pattern)
  const [prevSlotKey, setPrevSlotKey] = useState(`${date}|${serviceId}|${totalDuration}`)
  const slotKey = `${date}|${serviceId}|${totalDuration}`
  if (slotKey !== prevSlotKey) {
    setPrevSlotKey(slotKey)
    if (date !== appointment?.appointment_date) {
      setTime('')
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
  const discountChanged = (() => {
    const origMode = initDiscountMode
    if (discountMode !== origMode) return true
    if (discountMode === 'custom' && Number(customDiscountPct) !== (a.discount_pct ?? 0)) return true
    return false
  })()

  const hasChanges = dateChanged || timeChanged || notesChanged || serviceChanged || areasChanged || discountChanged

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

    if (discountMode === 'custom' && (!customDiscountPct || Number(customDiscountPct) <= 0 || Number(customDiscountPct) > 100)) {
      setError('Informe um desconto válido entre 1 e 100%.')
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

      if (discountChanged) {
        if (discountMode === 'partnership') {
          payload.discountPct = 100
          payload.discountReason = 'partnership'
        } else if (discountMode === 'custom') {
          payload.discountPct = Number(customDiscountPct)
          payload.discountReason = 'custom'
        } else {
          payload.discountPct = 0
          payload.discountReason = null
        }
      }

      await updateAppointment.mutateAsync({
        appointmentId: a.id,
        payload,
      })
      onClose()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response: { data?: { message?: string; error?: string } } }).response
        const detail = response.data?.error || response.data?.message
        setError(detail ?? 'Erro ao atualizar agendamento')
      } else {
        setError('Erro ao atualizar agendamento')
      }
    }
  }

  return (
    <Modal open onClose={onClose} title="Editar agendamento" width="lg">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-5">
        {/* Patient info (read-only) */}
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-sm font-medium text-gray-800">{displayName}</p>
        </div>

        {/* Date */}
        <Input
          label="Data"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

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

        {/* Time slot picker */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Horário</label>
          {!date || !serviceId ? (
            <p className="text-sm text-gray-300 py-3">Selecione data e serviço para ver horários</p>
          ) : slotsLoading ? (
            <div className="flex items-center gap-2 py-3">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-400">Carregando horários...</span>
            </div>
          ) : slotsWithCurrent.length === 0 ? (
            <p className="text-sm text-gray-400 py-3">Nenhum horário disponível para esta data</p>
          ) : (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
              {slotsWithCurrent.map((slot) => (
                <button
                  key={slot}
                  type="button"
                  onClick={() => setTime(slot)}
                  className={[
                    'px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                    time === slot
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                  ].join(' ')}
                >
                  {slot}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Discount section */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Desconto</label>
          <div className="flex gap-2">
            {([
              { key: 'none', label: 'Sem desconto' },
              { key: 'partnership', label: 'Parceria (100%)' },
              { key: 'custom', label: 'Personalizado' },
            ] as const).map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setDiscountMode(key)}
                className={[
                  'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border',
                  discountMode === key
                    ? key === 'partnership'
                      ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : key === 'custom'
                        ? 'bg-brand-50 border-brand-300 text-brand-700'
                        : 'bg-gray-900 border-gray-900 text-white'
                    : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600',
                ].join(' ')}
              >
                {label}
              </button>
            ))}
          </div>
          {discountMode === 'custom' && (
            <div className="mt-2 flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="99"
                placeholder="Ex: 30"
                value={customDiscountPct}
                onChange={(e) => setCustomDiscountPct(e.target.value)}
                className="w-24 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
              <span className="text-sm text-gray-500">% de desconto</span>
            </div>
          )}
        </div>

        {/* Price summary */}
        {selectedAreaIds.length > 0 && serviceAreas && (() => {
          const subtotal = serviceAreas
            .filter((a) => selectedAreaIds.includes(a.area_id))
            .reduce((sum, a) => sum + a.effective_price_cents, 0)
          const discountPct = discountMode === 'partnership' ? 100
            : discountMode === 'custom' && customDiscountPct ? Number(customDiscountPct)
            : 0
          const discountAmount = subtotal * discountPct / 100
          const total = subtotal - discountAmount
          const fmt = (v: number) => (v / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

          return (
            <div className="rounded-lg bg-gray-50 px-4 py-3 space-y-1.5">
              <div className="flex justify-between text-sm text-gray-500">
                <span>{selectedAreaIds.length} área{selectedAreaIds.length !== 1 ? 's' : ''}</span>
                <span>{fmt(subtotal)}</span>
              </div>
              {discountPct > 0 && (
                <div className="flex justify-between text-sm text-amber-600">
                  <span>Desconto ({discountPct}%)</span>
                  <span>-{fmt(discountAmount)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm font-semibold text-gray-900 border-t border-gray-200 pt-1.5">
                <span>Total</span>
                <span>{fmt(total)}</span>
              </div>
            </div>
          )
        })()}

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
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={updateAppointment.isPending} disabled={!hasChanges}>
            Salvar alterações
          </Button>
        </div>
      </form>
    </Modal>
  )
}
