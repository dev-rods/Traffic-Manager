import { useState } from 'react'
import type { FormEvent } from 'react'
import { Modal } from './ui/Modal'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { EmptyState } from './ui/EmptyState'
import { ErrorState } from './ui/ErrorState'
import { Spinner } from './ui/Spinner'
import { OtpCodeForm } from './OtpCodeForm'
import { useCancelAppointment, useMyAppointments } from '@/hooks/useBooking'
import { formatCurrencyBRL, formatDateLong, formatPhoneInput, isValidBrPhone, toApiPhone } from '@/utils/format'

type Step = 'phone' | 'otp' | 'list'

interface MyAppointmentsModalProps {
  open: boolean
  clinicId: string
  onClose: () => void
}

export function MyAppointmentsModal({ open, clinicId, onClose }: MyAppointmentsModalProps) {
  const [step, setStep] = useState<Step>('phone')
  const [phone, setPhone] = useState('')
  const [token, setToken] = useState<string | null>(null)
  const [cancelingId, setCancelingId] = useState<string | null>(null)

  // O campo mostra `(11) 99999-0000`; a API recebe `5511999990000`. Mandar o
  // formatado deixou a lista vazia para quem tinha acabado de agendar.
  const apiPhone = toApiPhone(phone)
  const myAppointments = useMyAppointments(clinicId, apiPhone, step === 'list' ? token : null)
  const cancelAppointment = useCancelAppointment(clinicId)

  function handleClose() {
    setStep('phone')
    setPhone('')
    setToken(null)
    setCancelingId(null)
    onClose()
  }

  function handlePhoneSubmit(e: FormEvent) {
    e.preventDefault()
    if (isValidBrPhone(phone)) setStep('otp')
  }

  function handleVerified(newToken: string) {
    setToken(newToken)
    setStep('list')
  }

  function handleCancel(appointmentId: string) {
    if (!token) return
    cancelAppointment.mutate(
      { appointmentId, phone: apiPhone, token },
      { onSuccess: () => setCancelingId(null) }
    )
  }

  return (
    <Modal open={open} onClose={handleClose} title="Meus agendamentos">
      {step === 'phone' ? (
        <form onSubmit={handlePhoneSubmit} className="flex flex-col gap-4">
          <p className="text-sm text-ink-600">Digite o celular usado para agendar o serviço.</p>
          <Input
            label="Celular (WhatsApp)"
            placeholder="Digite seu celular"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
          />
          <Button type="submit" disabled={!isValidBrPhone(phone)}>
            Continuar
          </Button>
        </form>
      ) : null}

      {step === 'otp' ? <OtpCodeForm clinicId={clinicId} phone={phone} onVerified={handleVerified} /> : null}

      {step === 'list' ? (
        <div className="flex flex-col gap-4">
          {myAppointments.isLoading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : myAppointments.isError ? (
            <ErrorState
              message="Não foi possível carregar seus agendamentos."
              onRetry={() => myAppointments.refetch()}
            />
          ) : !myAppointments.data || myAppointments.data.length === 0 ? (
            <EmptyState
              title="Nenhum agendamento encontrado"
              description="Você ainda não tem agendamentos futuros para este número."
            />
          ) : (
            myAppointments.data.map((appt) => (
              <div key={appt.id} className="rounded-2xl border border-ink-200 p-4">
                <p className="font-medium text-ink-900">{appt.service_name ?? 'Agendamento'}</p>
                {/* O mesmo telefone pode agendar para mais de uma pessoa. */}
                {appt.full_name ? <p className="text-sm text-ink-700">{appt.full_name}</p> : null}
                <p className="mt-1 text-sm text-ink-500">
                  {formatDateLong(appt.appointment_date)}, {appt.start_time.slice(0, 5)}
                  {appt.final_price_cents != null ? ` · ${formatCurrencyBRL(appt.final_price_cents)}` : ''}
                </p>
                {cancelingId === appt.id ? (
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="danger"
                      loading={cancelAppointment.isPending}
                      onClick={() => handleCancel(appt.id)}
                    >
                      Confirmar cancelamento
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setCancelingId(null)}>
                      Voltar
                    </Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setCancelingId(appt.id)}
                    className="mt-3 text-sm font-medium text-danger-500 underline underline-offset-2"
                  >
                    Cancelar agendamento
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      ) : null}
    </Modal>
  )
}
