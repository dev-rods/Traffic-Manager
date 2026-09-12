import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAvailableSlots, useClinicBootstrap, useCreateAppointment } from '@/hooks/useBooking'
import { useCart } from '@/store/useCart'
import { ProfessionalPicker } from '@/components/ProfessionalPicker'
import { WeekPicker } from '@/components/WeekPicker'
import { TimeSlotGrid } from '@/components/TimeSlotGrid'
import { CartSummary } from '@/components/CartSummary'
import { CustomerInfoForm } from '@/components/CustomerInfoForm'
import type { CustomerInfoFormData } from '@/components/CustomerInfoForm'
import { OtpConfirmModal } from '@/components/OtpConfirmModal'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatDateLong, toApiPhone } from '@/utils/format'
import type { WizardStep } from '@/types'

export function Booking() {
  const { clinicId } = useParams<{ clinicId: string }>()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId as string)
  const cart = useCart()
  const createAppointment = useCreateAppointment(clinicId as string)

  const [step, setStep] = useState<WizardStep>('cart')
  const [otpOpen, setOtpOpen] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const primaryServiceId = cart.items[0]?.id ?? ''
  const slots = useAvailableSlots(clinicId as string, cart.date, primaryServiceId, cart.totalDurationMinutes)

  useEffect(() => {
    if (cart.items.length === 0 && step !== 'success') {
      navigate(`/${clinicId}`, { replace: true })
    }
    // Só precisa reagir a mudanças no tamanho do carrinho, não a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart.items.length])

  if (bootstrap.isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    )
  }

  if (bootstrap.isError || !bootstrap.data) {
    return <ErrorState message="Não foi possível carregar este salão." onRetry={() => bootstrap.refetch()} />
  }

  const { professionals } = bootstrap.data
  const selectedProfessional = professionals.find((p) => p.id === cart.professionalId)

  function goToScheduleOrProfessional() {
    if (professionals.length > 1) {
      setStep('professional')
      return
    }
    if (professionals.length === 1) cart.setProfessionalId(professionals[0].id)
    setStep('schedule')
  }

  function handleCustomerSubmit(data: CustomerInfoFormData) {
    cart.setCustomer(data.fullName, toApiPhone(data.phone))
    setSubmitError(null)
    setOtpOpen(true)
  }

  function handleVerified(token: string) {
    cart.setOtpToken(token)
    setOtpOpen(false)
    if (!cart.date || !cart.time) return

    createAppointment.mutate(
      {
        token,
        phone: cart.customerPhone,
        fullName: cart.customerName,
        serviceIds: cart.items.map((s) => s.id),
        date: cart.date,
        time: cart.time,
        professionalId: cart.professionalId ?? undefined,
      },
      {
        onSuccess: () => setStep('success'),
        onError: (err) => setSubmitError((err as Error).message),
      }
    )
  }

  if (step === 'success') {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <span className="text-4xl" aria-hidden>
          ✓
        </span>
        <h1 className="font-display text-2xl text-ink-900">Agendamento confirmado!</h1>
        {cart.date && cart.time ? (
          <p className="text-ink-600">
            {formatDateLong(cart.date)}, {cart.time}
          </p>
        ) : null}
        <Button
          onClick={() => {
            cart.clearCart()
            navigate(`/${clinicId}`)
          }}
        >
          Voltar ao início
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="mb-3 text-sm text-ink-500">
          {cart.items.length === 1 ? 'Serviço selecionado' : `${cart.items.length} serviços selecionados`}
        </p>
        <CartSummary
          items={cart.items}
          onRemove={step === 'cart' ? cart.removeItem : undefined}
          professionalName={selectedProfessional?.name}
          date={step === 'customer' ? cart.date : undefined}
          time={step === 'customer' ? cart.time : undefined}
          totalDurationMinutes={cart.totalDurationMinutes}
          totalPriceCents={cart.totalPriceCents}
        />
      </div>

      {step === 'cart' ? (
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            to={`/${clinicId}`}
            className="inline-flex h-12 items-center justify-center rounded-full border border-ink-200 px-6 text-sm font-medium text-ink-700 transition-colors hover:border-ink-400"
          >
            Adicionar outro serviço
          </Link>
          <Button onClick={goToScheduleOrProfessional}>Continuar</Button>
        </div>
      ) : null}

      {step === 'professional' ? (
        <div>
          <h2 className="mb-4 text-center text-sm font-semibold uppercase tracking-wide text-ink-500">
            Selecione o profissional
          </h2>
          <ProfessionalPicker
            professionals={professionals}
            selectedId={cart.professionalId}
            onSelect={cart.setProfessionalId}
          />
          <div className="mt-6 flex justify-center">
            <Button disabled={!cart.professionalId} onClick={() => setStep('schedule')}>
              Continuar
            </Button>
          </div>
        </div>
      ) : null}

      {step === 'schedule' ? (
        <div className="flex flex-col gap-6">
          <WeekPicker selectedDate={cart.date} onSelectDate={cart.setDate} />
          {cart.date ? (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
                Selecione o horário de início
              </h2>
              <TimeSlotGrid
                slots={slots.data}
                isLoading={slots.isLoading}
                isError={slots.isError}
                selectedTime={cart.time}
                onSelect={(time) => cart.setSchedule(cart.date as string, time)}
              />
            </div>
          ) : null}
          <div className="flex justify-end">
            <Button disabled={!cart.date || !cart.time} onClick={() => setStep('customer')}>
              Continuar
            </Button>
          </div>
        </div>
      ) : null}

      {step === 'customer' ? (
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
            Informações do usuário
          </h2>
          <CustomerInfoForm
            defaultValues={{ fullName: cart.customerName }}
            onSubmit={handleCustomerSubmit}
            submitting={createAppointment.isPending}
          />
          {submitError ? <p className="mt-3 text-sm text-danger-500">{submitError}</p> : null}
          <button
            type="button"
            onClick={() => setStep('schedule')}
            className="mt-4 text-sm font-medium text-ink-500 underline underline-offset-2"
          >
            Voltar
          </button>
        </div>
      ) : null}

      <OtpConfirmModal
        open={otpOpen}
        clinicId={clinicId as string}
        phone={cart.customerPhone}
        onClose={() => setOtpOpen(false)}
        onVerified={handleVerified}
      />
    </div>
  )
}
