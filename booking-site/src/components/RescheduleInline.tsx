import { useState } from 'react'
import { DayList } from './DayList'
import { TimeSlotGrid } from './TimeSlotGrid'
import { Button } from './ui/Button'
import { ErrorState } from './ui/ErrorState'
import { useAvailability, useClinicBootstrap, useRescheduleAppointment } from '@/hooks/useBooking'
import { ApiError } from '@/services/api'
import type { Appointment, CartPayload } from '@/types'

interface RescheduleInlineProps {
  clinicId: string
  appointment: Appointment
  phone: string
  token: string
  onDone: () => void
  onBack: () => void
}

/**
 * Remarcar sem cancelar (PRD 035). O mesmo seletor de dia e horário do
 * agendamento, com o carrinho deste agendamento e a grade ignorando o próprio
 * horário — mover 10:00 para 10:30 no mesmo dia não pode colidir consigo mesmo.
 * O registro continua o mesmo; só a data muda.
 */
export function RescheduleInline({
  clinicId,
  appointment,
  phone,
  token,
  onDone,
  onBack,
}: RescheduleInlineProps) {
  const [date, setDate] = useState<string | null>(null)
  const [time, setTime] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)

  const cart: CartPayload = {
    serviceIds: appointment.service_ids?.length ? appointment.service_ids : [appointment.service_id],
    serviceAreaPairs: appointment.service_area_pairs ?? [],
  }

  const bootstrap = useClinicBootstrap(clinicId)
  const availability = useAvailability(clinicId, cart, true, appointment.id)
  const reschedule = useRescheduleAppointment(clinicId)

  function selectDate(iso: string) {
    setDate(iso)
    setTime(null)
    setConflict(null)
  }

  function confirm() {
    if (!date || !time) return
    setConflict(null)
    reschedule.mutate(
      { appointmentId: appointment.id, phone, token, date, time },
      {
        onSuccess: onDone,
        onError: (error) => {
          // A grade recarrega sozinha: a mutação invalida a disponibilidade
          // da clínica ao terminar (useRescheduleAppointment).
          if (error instanceof ApiError && error.status === 409) {
            setConflict(error.message)
            setTime(null)
          }
        },
      }
    )
  }

  const otherError = reschedule.isError && !conflict

  return (
    <div className="mt-3 flex flex-col gap-4 border-t border-ink-200 pt-3">
      <p className="text-sm font-medium text-ink-900">Escolha o novo dia</p>
      <DayList
        days={availability.data?.days}
        isLoading={availability.isLoading}
        isError={availability.isError}
        onRetry={() => availability.refetch()}
        selectedDate={date}
        onSelectDate={selectDate}
        clinicPhone={bootstrap.data?.clinic.phone ?? null}
      />

      {date ? (
        <div>
          <p className="mb-2 text-sm font-medium text-ink-900">Selecione o horário</p>
          <TimeSlotGrid
            slots={availability.data?.days[date]?.slots}
            isLoading={availability.isFetching && !availability.data}
            isError={availability.isError}
            selectedTime={time}
            onSelect={(t) => {
              setTime(t)
              setConflict(null)
            }}
          />
        </div>
      ) : null}

      {conflict ? (
        <p role="alert" className="text-sm text-danger-500">
          {conflict}
        </p>
      ) : null}

      {otherError ? (
        <ErrorState message="Não foi possível remarcar." onRetry={confirm} />
      ) : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button size="sm" variant="ghost" onClick={onBack} disabled={reschedule.isPending}>
          Voltar
        </Button>
        <Button size="sm" onClick={confirm} disabled={!date || !time} loading={reschedule.isPending}>
          Confirmar remarcação
        </Button>
      </div>
    </div>
  )
}
