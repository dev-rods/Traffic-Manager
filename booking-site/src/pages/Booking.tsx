import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useClinicBootstrap, useCreateAppointment, useMonthAvailability, useQuote } from '@/hooks/useBooking'
import { useClinicId } from '@/hooks/useClinicId'
import { useCart } from '@/store/useCart'
import { AreaPicker } from '@/components/AreaPicker'
import { DayList } from '@/components/DayList'
import { TimeSlotGrid } from '@/components/TimeSlotGrid'
import { CartSummary } from '@/components/CartSummary'
import { PriceBreakdown } from '@/components/PriceBreakdown'
import { CustomerInfoForm } from '@/components/CustomerInfoForm'
import type { CustomerInfoFormData } from '@/components/CustomerInfoForm'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { IconCheckCircle, IconChevronLeft } from '@/components/ui/icons'
import { ApiError } from '@/services/api'
import { formatCurrencyBRL, formatDateLong, formatPhoneDisplay, toApiPhone } from '@/utils/format'
import { cartHasAreas, cartPendingAreaSelection, toCartPayload } from '@/utils/cartTotals'
import { monthWindow } from '@/utils/monthWindow'
import { startOfToday } from '@/utils/weekDates'
import type { WizardStep } from '@/types'

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function Booking() {
  const { clinicId, basePath } = useClinicId()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId)
  const cart = useCart()
  const createAppointment = useCreateAppointment(clinicId)

  const [step, setStep] = useState<WizardStep>('cart')
  const [submitError, setSubmitError] = useState<string | null>(null)
  // Telefone usado na cotação: com ele entram primeira sessão e desconto
  // personalizado, antes de o cliente confirmar.
  const [quotePhone, setQuotePhone] = useState<string | undefined>(undefined)
  // Datas perguntadas ao backend: de hoje até o fim do mês. Quem decide o que
  // é agendável é o backend (no fuso da clínica); isto só limita a pergunta.
  const [monthDates] = useState(() => monthWindow(startOfToday()))
  const slotsRef = useRef<HTMLDivElement>(null)

  const serviceAreas = bootstrap.data?.serviceAreas ?? []
  const professionals = bootstrap.data?.professionals ?? []
  const pendingAreas = cartPendingAreaSelection(cart.items, serviceAreas)
  const cartReady = bootstrap.isSuccess && cart.items.length > 0 && pendingAreas.length === 0
  const cartPayload = toCartPayload(cart.items, serviceAreas)

  const availability = useMonthAvailability(clinicId, monthDates, cartPayload, cartReady)
  const quote = useQuote(clinicId, cartPayload, quotePhone, cartReady)

  // Com um único serviço no catálogo não existe outro pra escolher - o
  // carrinho não é uma decisão, é um fato. A etapa de revisão (e o botão
  // "Adicionar outro serviço") não tem o que oferecer, então é pulada: o
  // fluxo começa direto na próxima etapa de verdade (áreas, ou agendamento).
  const isSingleService = bootstrap.data?.services.length === 1

  useEffect(() => {
    if (cart.items.length === 0 && step !== 'success') {
      navigate(basePath || '/', { replace: true })
    }
    // Só precisa reagir a mudanças no tamanho do carrinho, não a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart.items.length])

  // Ao escolher o dia, os horários aparecem abaixo da lista — no celular,
  // fora da tela. Leva o cliente até eles.
  useEffect(() => {
    if (step !== 'schedule' || !cart.date) return
    slotsRef.current?.scrollIntoView?.({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      block: 'nearest',
    })
  }, [cart.date, step])

  // Profissional não é escolhido pelo cliente: o backend atribui (o conflito
  // de horário é checado na clínica inteira, então a escolha não reservava a
  // agenda de ninguém).
  function goToAreasOrSchedule() {
    setStep(pendingAreas.length > 0 ? 'areas' : 'schedule')
  }

  useEffect(() => {
    if (isSingleService && step === 'cart' && cart.items.length > 0) {
      goToAreasOrSchedule()
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

  const { clinic } = bootstrap.data

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
    } else if (step === 'schedule') {
      if (cartHasAreas(cart.items, serviceAreas)) setStep('areas')
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

  function handlePhoneChange(phone: string | null) {
    setQuotePhone(phone ? toApiPhone(phone) : undefined)
  }

  function handleCustomerSubmit(data: CustomerInfoFormData) {
    const phone = toApiPhone(data.phone)
    cart.setCustomer(data.fullName, phone)
    setSubmitError(null)

    if (!cart.date || !cart.time) return

    createAppointment.mutate(
      { ...cartPayload, phone, fullName: data.fullName, date: cart.date, time: cart.time },
      {
        onSuccess: () => setStep('success'),
        onError: (err) => {
          // O horário foi ocupado enquanto o cliente preenchia os dados. A
          // grade já foi invalidada (useCreateAppointment); volta para ela.
          if (err instanceof ApiError && err.status === 409) {
            cart.clearSchedule()
            setStep('schedule')
            setSubmitError('Esse horário acabou de ser ocupado. Escolha outro, por favor.')
            return
          }
          setSubmitError(err.message)
        },
      }
    )
  }

  if (step === 'success') {
    const finalPrice = createAppointment.data?.final_price_cents
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <IconCheckCircle className="h-12 w-12 text-success-500" />
        <h1 className="font-display text-2xl text-ink-900">Agendamento confirmado!</h1>
        {cart.date && cart.time ? (
          <p className="text-ink-600">
            {formatDateLong(cart.date)}, {cart.time}
          </p>
        ) : null}
        {finalPrice != null ? (
          <p className="tabular-nums text-ink-600">Valor: {formatCurrencyBRL(finalPrice)}</p>
        ) : null}
        <p className="max-w-sm text-sm text-ink-500">
          Enviamos a confirmação e as orientações para a sessão por WhatsApp para{' '}
          {formatPhoneDisplay(cart.customerPhone)}.
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

  const price =
    pendingAreas.length > 0 ? (
      <p className="text-sm text-ink-500">Escolha as áreas para ver o valor.</p>
    ) : (
      <PriceBreakdown quote={quote.data} isLoading={quote.isLoading} isError={quote.isError} />
    )

  return (
    <div className="flex flex-col gap-8">
      <button
        type="button"
        onClick={goBack}
        className="-ml-2 inline-flex h-11 w-fit cursor-pointer items-center gap-1 rounded-lg px-2 text-sm font-medium text-ink-500 transition-colors hover:text-ink-900"
      >
        <IconChevronLeft />
        Voltar
      </button>

      <div>
        <p className="mb-3 text-sm text-ink-500">
          {cart.items.length === 1 ? 'Serviço selecionado' : `${cart.items.length} serviços selecionados`}
        </p>
        <CartSummary
          items={cart.items}
          serviceAreas={serviceAreas}
          onRemove={step === 'cart' ? cart.removeItem : undefined}
          date={step === 'customer' ? cart.date : undefined}
          time={step === 'customer' ? cart.time : undefined}
          price={price}
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
          <Button onClick={goToAreasOrSchedule}>Continuar</Button>
        </div>
      ) : null}

      {step === 'areas' ? (
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
            Selecione as áreas de tratamento
          </h2>
          <AreaPicker items={cart.items} serviceAreas={serviceAreas} onToggleArea={handleToggleArea} />
          <div className="mt-6 flex justify-end">
            <Button disabled={pendingAreas.length > 0} onClick={() => setStep('schedule')}>
              Continuar
            </Button>
          </div>
        </div>
      ) : null}

      {step === 'schedule' ? (
        <div className="flex flex-col gap-6">
          {submitError ? (
            <p role="alert" className="rounded-lg bg-danger-100 px-4 py-3 text-sm text-danger-500">
              {submitError}
            </p>
          ) : null}
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">Escolha o dia</h2>
            <DayList
              days={availability.data?.days}
              bookingWindow={availability.data?.window}
              isLoading={availability.isLoading}
              isError={availability.isError}
              onRetry={() => availability.refetch()}
              selectedDate={cart.date}
              onSelectDate={cart.setDate}
              clinicPhone={clinic.phone}
            />
          </div>
          {cart.date ? (
            <div ref={slotsRef} className="scroll-mt-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
                Selecione o horário de início
              </h2>
              <TimeSlotGrid
                slots={availability.data?.days[cart.date]?.slots}
                isLoading={availability.isLoading}
                isError={availability.isError}
                selectedTime={cart.time}
                onSelect={(time) => cart.setSchedule(cart.date as string, time)}
              />
            </div>
          ) : null}
          <div className="flex justify-end">
            <Button
              disabled={!cart.date || !cart.time}
              onClick={() => {
                setSubmitError(null)
                setStep('customer')
              }}
            >
              Continuar
            </Button>
          </div>
        </div>
      ) : null}

      {step === 'customer' ? (
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">Seus dados</h2>
          <CustomerInfoForm
            defaultValues={{ fullName: cart.customerName }}
            onSubmit={handleCustomerSubmit}
            onPhoneChange={handlePhoneChange}
            submitting={createAppointment.isPending}
            submitLabel="Confirmar agendamento"
          />
          {submitError ? (
            <p role="alert" className="mt-3 text-sm text-danger-500">
              {submitError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
