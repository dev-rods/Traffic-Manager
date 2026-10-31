import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useClinicBootstrap,
  useCreateAppointment,
  useAvailability,
  useQuote,
} from '@/hooks/useBooking'
import { useClinicId } from '@/hooks/useClinicId'
import { useCart } from '@/store/useCart'
import { AreaPicker } from '@/components/AreaPicker'
import { DayList } from '@/components/DayList'
import { TimeSlotGrid } from '@/components/TimeSlotGrid'
import { CartSummary } from '@/components/CartSummary'
import { PriceBreakdown } from '@/components/PriceBreakdown'
import { CustomerInfoForm } from '@/components/CustomerInfoForm'
import { DiscountTiersNote } from '@/components/DiscountTiersNote'
import { ClinicWelcome } from '@/components/ClinicWelcome'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { StickyActionBar } from '@/components/StickyActionBar'
import { DuplicateBookingDialog } from '@/components/DuplicateBookingDialog'
import type { CustomerInfoFormData } from '@/components/CustomerInfoForm'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { IconCheckCircle, IconChevronLeft } from '@/components/ui/icons'
import { ApiError } from '@/services/api'
import { formatCurrencyBRL, formatDateLong, formatPhoneDisplay, toApiPhone } from '@/utils/format'
import { cartHasAreas, cartPendingAreaSelection, toCartPayload } from '@/utils/cartTotals'
import type { CreateAppointmentPayload, WizardStep } from '@/types'

// A criação responde 409 por dois motivos: horário ocupado (sem code) e
// número com agendamento futuro (este code, pede confirmação).
const HAS_FUTURE_APPOINTMENT = 'HAS_FUTURE_APPOINTMENT'

interface PendingDuplicate {
  payload: CreateAppointmentPayload
  existingCount: number
}

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
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
  const [pendingDuplicate, setPendingDuplicate] = useState<PendingDuplicate | null>(null)
  const slotsRef = useRef<HTMLDivElement>(null)

  const serviceAreas = bootstrap.data?.serviceAreas ?? []
  const pendingAreas = cartPendingAreaSelection(cart.items, serviceAreas)
  const cartReady = bootstrap.isSuccess && cart.items.length > 0 && pendingAreas.length === 0
  const cartPayload = toCartPayload(cart.items, serviceAreas)

  // Quais datas aparecem é decisão do backend (as próximas N com horário, no
  // fuso da clínica); o site só pergunta pelo carrinho e exibe.
  const availability = useAvailability(clinicId, cartPayload, cartReady)
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
    return (
      <ErrorState
        message="Não foi possível carregar este salão."
        onRetry={() => bootstrap.refetch()}
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

  // Com um serviço só não há tela anterior de verdade: a lista de serviços
  // teria um item, já escolhido. Onde o "Voltar" levaria para lá, ele some.
  const backLeavesWizard =
    step === 'cart' ||
    step === 'areas' ||
    (step === 'schedule' && !cartHasAreas(cart.items, serviceAreas))
  const showBack = !(isSingleService && backLeavesWizard)

  const selectedAreaCount = cart.items.reduce((sum, item) => sum + item.areaIds.length, 0)
  // O valor é o da cotação (com combos e desconto), o mesmo do resumo acima.
  const areasSummary =
    selectedAreaCount === 0 ? (
      <span>Escolha ao menos uma área</span>
    ) : (
      <>
        <span>
          {selectedAreaCount === 1
            ? '1 área selecionada'
            : `${selectedAreaCount} áreas selecionadas`}
        </span>
        {pendingAreas.length === 0 &&
        !quote.isPlaceholderData &&
        quote.data?.finalPriceCents != null ? (
          <span className="font-semibold tabular-nums text-ink-900">
            {formatCurrencyBRL(quote.data.finalPriceCents)}
          </span>
        ) : null}
      </>
    )

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

    submitAppointment({
      ...cartPayload,
      phone,
      fullName: data.fullName,
      date: cart.date,
      time: cart.time,
    })
  }

  function submitAppointment(payload: CreateAppointmentPayload) {
    createAppointment.mutate(payload, {
      onSuccess: () => {
        setPendingDuplicate(null)
        setStep('success')
      },
      onError: (err) => {
        setPendingDuplicate(null)
        // O número já tem agendamento futuro: pergunta antes de criar outro.
        if (err instanceof ApiError && err.code === HAS_FUTURE_APPOINTMENT) {
          setPendingDuplicate({ payload, existingCount: err.body?.existingCount ?? 1 })
          return
        }
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
    })
  }

  if (step === 'success') {
    const finalPrice = createAppointment.data?.final_price_cents
    return (
      <div className="flex flex-col gap-6">
        <div className="border-b border-ink-200 pb-6">
          <ClinicWelcome clinic={clinic} />
        </div>
        <div className="flex flex-col items-center gap-4 py-10 text-center">
          <IconCheckCircle className="h-12 w-12 text-success-500" />
          <h2 className="font-display text-2xl font-bold text-ink-900">Agendamento confirmado!</h2>
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 border-b border-ink-200 pb-6">
        {showBack ? (
          <button
            type="button"
            onClick={goBack}
            className="-ml-2 inline-flex h-11 w-fit cursor-pointer items-center gap-1 rounded-lg px-2 text-sm font-medium text-ink-500 transition-colors hover:text-ink-900"
          >
            <IconChevronLeft />
            Voltar
          </button>
        ) : null}
        <ClinicWelcome clinic={clinic} />
      </div>

      <div>
        <SectionTitle>
          {cart.items.length === 1
            ? 'Serviço selecionado'
            : `${cart.items.length} serviços selecionados`}
        </SectionTitle>
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
        <div className="flex flex-col gap-3">
          <Link
            to={basePath || '/'}
            className="inline-flex h-12 items-center justify-center rounded-lg bg-muted-100 px-6 font-display text-[0.95rem] font-semibold text-muted-700 transition-colors hover:bg-muted-200"
          >
            Adicionar outro serviço
          </Link>
          <Button onClick={goToAreasOrSchedule}>Continuar</Button>
        </div>
      ) : null}

      {step === 'areas' ? (
        <div>
          <SectionTitle>Selecione as áreas de tratamento</SectionTitle>
          <DiscountTiersNote
            tiers={bootstrap.data.discountTiers}
            areaCount={pendingAreas.length > 0 ? 0 : quote.data?.areaCount}
          />
          <AreaPicker
            items={cart.items}
            serviceAreas={serviceAreas}
            onToggleArea={handleToggleArea}
          />
          <StickyActionBar summary={areasSummary}>
            <Button disabled={pendingAreas.length > 0} onClick={() => setStep('schedule')}>
              Continuar
            </Button>
          </StickyActionBar>
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
            <SectionTitle>Escolha o dia</SectionTitle>
            <DayList
              days={availability.data?.days}
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
              <SectionTitle>Selecione o horário</SectionTitle>
              <TimeSlotGrid
                slots={availability.data?.days[cart.date]?.slots}
                isLoading={availability.isLoading}
                isError={availability.isError}
                selectedTime={cart.time}
                onSelect={(time) => cart.setSchedule(cart.date as string, time)}
              />
            </div>
          ) : null}
          <div className="flex flex-col">
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
          <SectionTitle>Seus dados</SectionTitle>
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
          <DuplicateBookingDialog
            existingCount={pendingDuplicate?.existingCount ?? null}
            confirming={createAppointment.isPending}
            onConfirm={() =>
              pendingDuplicate &&
              submitAppointment({ ...pendingDuplicate.payload, confirmDuplicate: true })
            }
            onCancel={() => setPendingDuplicate(null)}
          />
        </div>
      ) : null}
    </div>
  )
}
