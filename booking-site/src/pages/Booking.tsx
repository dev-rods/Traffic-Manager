import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useClinicBootstrap, useCreateAppointment, useWeekAvailability } from '@/hooks/useBooking'
import { useClinicId } from '@/hooks/useClinicId'
import { useCart } from '@/store/useCart'
import { ProfessionalPicker } from '@/components/ProfessionalPicker'
import { AreaPicker } from '@/components/AreaPicker'
import { WeekPicker } from '@/components/WeekPicker'
import { startOfWeekMonday, startOfToday, toISODate, weekDates } from '@/utils/weekDates'
import { TimeSlotGrid } from '@/components/TimeSlotGrid'
import { CartSummary } from '@/components/CartSummary'
import { CustomerInfoForm } from '@/components/CustomerInfoForm'
import type { CustomerInfoFormData } from '@/components/CustomerInfoForm'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatDateLong, toApiPhone } from '@/utils/format'
import { buildServiceAreaPairs, cartHasAreas, cartPendingAreaSelection, computeCartTotals } from '@/utils/cartTotals'
import type { WizardStep } from '@/types'

export function Booking() {
  const { clinicId, basePath } = useClinicId()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId)
  const cart = useCart()
  const createAppointment = useCreateAppointment(clinicId)

  const [step, setStep] = useState<WizardStep>('cart')
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeekMonday(startOfToday()))
  const [submitError, setSubmitError] = useState<string | null>(null)

  const serviceAreas = bootstrap.data?.serviceAreas ?? []
  const professionals = bootstrap.data?.professionals ?? []
  const { durationMinutes, priceCents } = computeCartTotals(cart.items, serviceAreas)

  // Com um único serviço no catálogo não existe outro pra escolher - o
  // carrinho não é uma decisão, é um fato. A etapa de revisão (e o botão
  // "Adicionar outro serviço") não tem o que oferecer, então é pulada: o
  // fluxo começa direto na próxima etapa de verdade (áreas, ou agendamento).
  const isSingleService = bootstrap.data?.services.length === 1

  const weekIsoDates = weekDates(weekStart).map(toISODate)
  const weekAvailability = useWeekAvailability(clinicId, weekIsoDates, durationMinutes)

  useEffect(() => {
    if (cart.items.length === 0 && step !== 'success') {
      navigate(basePath || '/', { replace: true })
    }
    // Só precisa reagir a mudanças no tamanho do carrinho, não a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart.items.length])

  function goToAreasOrNext() {
    if (cartPendingAreaSelection(cart.items, serviceAreas).length > 0) {
      setStep('areas')
    } else {
      goToScheduleOrProfessional()
    }
  }

  function goToScheduleOrProfessional() {
    if (professionals.length > 1) {
      setStep('professional')
      return
    }
    if (professionals.length === 1) cart.setProfessionalId(professionals[0].id)
    setStep('schedule')
  }

  useEffect(() => {
    if (isSingleService && step === 'cart' && cart.items.length > 0) {
      goToAreasOrNext()
    }
    // Só no momento em que os dados chegam (ou o carrinho passa a ter o item
    // pré-selecionado) - não a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSingleService, cart.items.length])

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

  const selectedProfessional = professionals.find((p) => p.id === cart.professionalId)
  const pendingAreas = cartPendingAreaSelection(cart.items, serviceAreas)

  // Sem profissional cadastrado não há quem receber o agendamento - a
  // AvailabilityEngine nunca abre um horário, e sem isto o cliente veria o
  // calendário inteiro "fechado" sem entender por quê.
  if (professionals.length === 0) {
    return (
      <EmptyState
        title="Agendamento online indisponível no momento"
        description="Este salão ainda não está aceitando agendamentos pela internet. Entre em contato diretamente para marcar seu horário."
      />
    )
  }

  // Frame transitório entre montar com step inicial 'cart' e o efeito acima
  // pular pra etapa de verdade - sem isto o cliente veria um flash da tela
  // de revisão (que nem faz sentido existir quando não há o que revisar).
  if (isSingleService && step === 'cart') {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    )
  }

  function goToCartOrHome() {
    if (isSingleService) {
      navigate(basePath || '/')
    } else {
      setStep('cart')
    }
  }

  function goBack() {
    if (step === 'cart') {
      navigate(basePath || '/')
    } else if (step === 'areas') {
      goToCartOrHome()
    } else if (step === 'professional') {
      if (cartHasAreas(cart.items, serviceAreas)) setStep('areas')
      else goToCartOrHome()
    } else if (step === 'schedule') {
      if (professionals.length > 1) setStep('professional')
      else if (cartHasAreas(cart.items, serviceAreas)) setStep('areas')
      else goToCartOrHome()
    } else if (step === 'customer') {
      setStep('schedule')
    }
  }

  function handleToggleArea(serviceId: string, areaId: string) {
    const item = cart.items.find((i) => i.service.id === serviceId)
    if (!item) return
    const next = item.areaIds.includes(areaId)
      ? item.areaIds.filter((id) => id !== areaId)
      : [...item.areaIds, areaId]
    cart.setItemAreas(serviceId, next)
  }

  function handleSelectDate(iso: string) {
    cart.setDate(iso)
  }

  function handlePrevWeek() {
    const prev = new Date(weekStart)
    prev.setDate(prev.getDate() - 7)
    setWeekStart(prev)
  }

  function handleNextWeek() {
    const next = new Date(weekStart)
    next.setDate(next.getDate() + 7)
    setWeekStart(next)
  }

  function handleCustomerSubmit(data: CustomerInfoFormData) {
    const phone = toApiPhone(data.phone)
    cart.setCustomer(data.fullName, phone)
    setSubmitError(null)

    if (!cart.date || !cart.time) return

    const serviceAreaPairs = buildServiceAreaPairs(cart.items, serviceAreas)

    createAppointment.mutate(
      {
        phone,
        fullName: data.fullName,
        serviceIds: cart.items.map((i) => i.service.id),
        date: cart.date,
        time: cart.time,
        professionalId: cart.professionalId ?? undefined,
        serviceAreaPairs: serviceAreaPairs.length > 0 ? serviceAreaPairs : undefined,
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
        <p className="max-w-sm text-sm text-ink-500">
          Enviamos a confirmação por WhatsApp para {cart.customerPhone}.
        </p>
        <Button
          onClick={() => {
            cart.clearCart()
            navigate(basePath || '/')
          }}
        >
          Voltar ao início
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <button
        type="button"
        onClick={goBack}
        className="inline-flex w-fit cursor-pointer items-center gap-1 text-sm font-medium text-ink-500 transition-colors hover:text-ink-900"
      >
        <span aria-hidden>‹</span> Voltar
      </button>

      <div>
        <p className="mb-3 text-sm text-ink-500">
          {cart.items.length === 1 ? 'Serviço selecionado' : `${cart.items.length} serviços selecionados`}
        </p>
        <CartSummary
          items={cart.items}
          serviceAreas={serviceAreas}
          onRemove={step === 'cart' ? cart.removeItem : undefined}
          professionalName={selectedProfessional?.name}
          date={step === 'customer' ? cart.date : undefined}
          time={step === 'customer' ? cart.time : undefined}
          totalDurationMinutes={durationMinutes}
          totalPriceCents={priceCents}
        />
      </div>

      {step === 'cart' ? (
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            to={basePath || '/'}
            className="inline-flex h-12 items-center justify-center rounded-lg border border-ink-200 px-6 text-sm font-medium text-ink-700 transition-colors hover:border-ink-400"
          >
            Adicionar outro serviço
          </Link>
          <Button onClick={goToAreasOrNext}>Continuar</Button>
        </div>
      ) : null}

      {step === 'areas' ? (
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
            Selecione as áreas de tratamento
          </h2>
          <AreaPicker items={cart.items} serviceAreas={serviceAreas} onToggleArea={handleToggleArea} />
          <div className="mt-6 flex justify-end">
            <Button disabled={pendingAreas.length > 0} onClick={goToScheduleOrProfessional}>
              Continuar
            </Button>
          </div>
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
          <WeekPicker
            weekStart={weekStart}
            onPrevWeek={handlePrevWeek}
            onNextWeek={handleNextWeek}
            days={weekAvailability.data}
            isLoading={weekAvailability.isLoading}
            selectedDate={cart.date}
            onSelectDate={handleSelectDate}
          />
          {cart.date ? (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
                Selecione o horário de início
              </h2>
              <TimeSlotGrid
                slots={weekAvailability.data?.[cart.date]?.slots}
                isLoading={weekAvailability.isLoading}
                isError={weekAvailability.isError}
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
        </div>
      ) : null}
    </div>
  )
}
