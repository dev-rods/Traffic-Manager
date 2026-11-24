import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useAvailability,
  useCadastro,
  useClinicBootstrap,
  useCreateAppointment,
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
import { RemarcacaoDialog } from '@/components/RemarcacaoDialog'
import { SessaoFuturaDialog } from '@/components/SessaoFuturaDialog'
import { OtpCodeForm } from '@/components/OtpCodeForm'
import { PhoneStep } from '@/components/PhoneStep'
import { IdentityConfirm } from '@/components/IdentityConfirm'
import type { CustomerInfoFormData } from '@/components/CustomerInfoForm'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { IconCheckCircle, IconChevronLeft } from '@/components/ui/icons'
import { ApiError } from '@/services/api'
import { formatCurrencyBRL, formatDateLong, formatPhoneDisplay, toApiPhone } from '@/utils/format'
import { cartHasAreas, cartPendingAreaSelection, toCartPayload } from '@/utils/cartTotals'
import { brDateToIso, listaDeCampos, onlyDigits } from '@/utils/cadastro'
import {
  guardaSessaoVerificada,
  leSessaoVerificada,
  sessaoValeParaOCelular,
} from '@/utils/sessaoVerificada'
import type {
  CadastroPayload,
  CampoDoCadastro,
  CreateAppointmentPayload,
  PacienteVerificado,
  SessaoExistente,
  WizardStep,
} from '@/types'

const SAME_MONTH_APPOINTMENT = 'SAME_MONTH_APPOINTMENT'
const OTHER_MONTH_APPOINTMENT = 'OTHER_MONTH_APPOINTMENT'
const CADASTRO_INCOMPLETO = 'CADASTRO_INCOMPLETO'
const CPF_EM_USO = 'CPF_EM_USO'
const TODOS_OS_CAMPOS: CampoDoCadastro[] = ['cpf', 'birth_date', 'email']

interface Conflito {
  payload: CreateAppointmentPayload
  existing: SessaoExistente
  tipo: 'mesmo_mes' | 'outro_mes'
}

// Quem é a pessoa, decidido pela cotação com o celular (PRD 061): paciente
// confirma o código e a identidade; quem não é se cadastra antes do código.
type Ramo = 'paciente' | 'novo'

type DadosDeCadastro = Pick<CustomerInfoFormData, 'cpf' | 'birthDate' | 'email'> & { fullName: string }

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function cadastroPayload(phone: string, token: string, dados: Partial<DadosDeCadastro>): CadastroPayload {
  return {
    phone,
    token,
    fullName: dados.fullName?.trim() || undefined,
    cpf: onlyDigits(dados.cpf ?? '') || undefined,
    birthDate: dados.birthDate ? (brDateToIso(dados.birthDate) ?? undefined) : undefined,
    email: dados.email?.trim() || undefined,
  }
}

export function Booking() {
  const { clinicId, basePath } = useClinicId()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId)
  const cart = useCart()
  const createAppointment = useCreateAppointment(clinicId)
  const cadastro = useCadastro(clinicId)

  const [step, setStep] = useState<WizardStep>('cart')
  const [submitError, setSubmitError] = useState<string | null>(null)
  // Telefone usado na cotação: com ele entram primeira sessão e desconto
  // personalizado. Desde o PRD 061 é digitado logo depois das áreas, então o
  // preço na lateral já é o da pessoa antes de qualquer data.
  const [quotePhone, setQuotePhone] = useState<string | undefined>(undefined)
  const [phone, setPhone] = useState<string>('')
  const [ramo, setRamo] = useState<Ramo>('novo')
  // O celular verificado nesta aba (PRD 061): vale também para o "Meus
  // agendamentos" e sobrevive a um recarregamento da página.
  const [verified, setVerified] = useState<{ phone: string; token: string } | null>(() => {
    const guardada = leSessaoVerificada()
    return guardada ? { phone: guardada.phone, token: guardada.token } : null
  })
  const [paciente, setPaciente] = useState<PacienteVerificado>(null)
  const [dadosDeCadastro, setDadosDeCadastro] = useState<DadosDeCadastro | null>(null)
  const [cadastroError, setCadastroError] = useState<string | null>(null)
  // Pedido que levou 401 (token vencido): o código é refeito e o pedido repetido.
  const [pendingPayload, setPendingPayload] = useState<Omit<CreateAppointmentPayload, 'token'> | null>(null)
  const [conflito, setConflito] = useState<Conflito | null>(null)
  const [remarcado, setRemarcado] = useState(false)
  const slotsRef = useRef<HTMLDivElement>(null)

  const serviceAreas = bootstrap.data?.serviceAreas ?? []
  const pendingAreas = cartPendingAreaSelection(cart.items, serviceAreas)
  const cartReady = bootstrap.isSuccess && cart.items.length > 0 && pendingAreas.length === 0
  const cartPayload = toCartPayload(cart.items, serviceAreas)

  // Quais datas aparecem é decisão do backend (as próximas N com horário, no
  // fuso da clínica); o site só pergunta pelo carrinho e exibe.
  const availability = useAvailability(clinicId, cartPayload, cartReady)
  const quote = useQuote(clinicId, cartPayload, quotePhone, cartReady)

  // Enquanto a cotação com o celular não volta, não dá para saber o ramo.
  const aguardandoCadastro = quotePhone !== undefined && (quote.isFetching || quote.isPlaceholderData)

  // Com um único serviço no catálogo não existe outro pra escolher - o
  // carrinho não é uma decisão, é um fato. A etapa de revisão (e o botão
  // "Adicionar outro serviço") não tem o que oferecer, então é pulada: o
  // fluxo começa direto na próxima etapa de verdade (áreas, ou celular).
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

  function goToAreasOrPhone() {
    setStep(pendingAreas.length > 0 ? 'areas' : 'phone')
  }

  useEffect(() => {
    if (isSingleService && step === 'cart' && cart.items.length > 0) {
      goToAreasOrPhone()
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
    (step === 'phone' && !cartHasAreas(cart.items, serviceAreas))
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

  const nomeDaPessoa = ramo === 'paciente' ? paciente?.nome ?? '' : dadosDeCadastro?.fullName ?? ''

  function goBack() {
    setSubmitError(null)
    setCadastroError(null)
    if (step === 'cart') {
      navigate(basePath || '/')
    } else if (step === 'areas') {
      goToCartOrHome()
    } else if (step === 'phone') {
      if (cartHasAreas(cart.items, serviceAreas)) setStep('areas')
      else goToCartOrHome()
    } else if (step === 'verify') {
      setPendingPayload(null)
      setStep(ramo === 'novo' ? 'register' : 'phone')
    } else if (step === 'identity' || step === 'register') {
      setStep('phone')
    } else if (step === 'schedule') {
      setStep(ramo === 'paciente' ? 'identity' : 'register')
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

  function handlePhoneChange(phoneDisplay: string | null) {
    setQuotePhone(phoneDisplay ? toApiPhone(phoneDisplay) : undefined)
  }

  // A cotação diz se o celular é de um paciente. Backend antigo (sem
  // `conhecido`) é lido pelo que `faltam` já revelava: quem não falta tudo é
  // conhecido.
  function celularConhecido(): boolean {
    const c = quote.data?.cadastro
    if (!c) return false
    if (typeof c.conhecido === 'boolean') return c.conhecido
    return c.completo || c.faltam.length < TODOS_OS_CAMPOS.length
  }

  function handlePhoneContinue(phoneDisplay: string) {
    const apiPhone = toApiPhone(phoneDisplay)
    setPhone(apiPhone)
    setSubmitError(null)
    setCadastroError(null)
    const conhecido = celularConhecido()
    setRamo(conhecido ? 'paciente' : 'novo')

    if (!conhecido) {
      setStep('register')
      return
    }

    if (verified && sessaoValeParaOCelular({ ...verified, expiraEm: Infinity }, apiPhone)) {
      // Já confirmou o código nesta aba: só falta saber quem é. Só com phone e
      // token a rota de cadastro devolve a ficha sem gravar nada.
      cadastro.mutate(
        { phone: apiPhone, token: verified.token },
        {
          onSuccess: (ficha) => {
            setPaciente(ficha)
            setStep(ficha ? 'identity' : 'register')
          },
          onError: () => setStep('verify'),
        }
      )
      return
    }
    setStep('verify')
  }

  function handleVerified(token: string, ficha: PacienteVerificado) {
    const sessao = { phone, token }
    setVerified(sessao)
    guardaSessaoVerificada(phone, token)

    // Token vencido no meio da confirmação: refaz o mesmo pedido.
    if (pendingPayload) {
      const payload = pendingPayload
      setPendingPayload(null)
      setStep('schedule')
      submitAppointment({ ...payload, token })
      return
    }

    if (ramo === 'novo') {
      if (!dadosDeCadastro) {
        setStep('register')
        return
      }
      cadastrar(cadastroPayload(phone, token, dadosDeCadastro), () => setStep('schedule'), 'register')
      return
    }

    setPaciente(ficha)
    // A cotação disse "conhecido", mas o cadastro sumiu no meio do caminho (ou
    // o número casa com duas fichas): pede o cadastro como a quem é novo.
    setStep(ficha ? 'identity' : 'register')
  }

  function cadastrar(payload: CadastroPayload, depois: () => void, voltarPara: WizardStep) {
    setCadastroError(null)
    cadastro.mutate(payload, {
      onSuccess: (ficha) => {
        if (ficha) setPaciente(ficha)
        depois()
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 401) {
          setStep('verify')
          return
        }
        if (err instanceof ApiError && err.code === CADASTRO_INCOMPLETO && Array.isArray(err.body?.faltam)) {
          setCadastroError(`Precisamos completar seu cadastro: ${listaDeCampos(err.body.faltam as CampoDoCadastro[])}.`)
        } else {
          setCadastroError(err.message)
        }
        setStep(voltarPara)
      },
    })
  }

  function handleIdentityConfirm(dados: Partial<DadosDeCadastro>) {
    if (!verified) {
      setStep('verify')
      return
    }
    const temAlgo = Boolean(dados.cpf || dados.birthDate || dados.email)
    if (!temAlgo) {
      setStep('schedule')
      return
    }
    cadastrar(cadastroPayload(phone, verified.token, dados), () => setStep('schedule'), 'identity')
  }

  function handleNotMe() {
    setPaciente(null)
    setPhone('')
    setQuotePhone(undefined)
    setCadastroError(null)
    setStep('phone')
  }

  function handleRegisterSubmit(data: CustomerInfoFormData) {
    const dados: DadosDeCadastro = {
      fullName: data.fullName ?? '',
      cpf: data.cpf,
      birthDate: data.birthDate,
      email: data.email,
    }
    setDadosDeCadastro(dados)
    cart.setCustomer(dados.fullName, phone)
    if (verified && verified.phone === phone) {
      cadastrar(cadastroPayload(phone, verified.token, dados), () => setStep('schedule'), 'register')
      return
    }
    setStep('verify')
  }

  function handleConfirmAppointment() {
    if (!cart.date || !cart.time) return
    setSubmitError(null)
    const payload: Omit<CreateAppointmentPayload, 'token'> = {
      ...cartPayload,
      phone,
      fullName: nomeDaPessoa,
      date: cart.date,
      time: cart.time,
    }
    cart.setCustomer(nomeDaPessoa, phone)
    if (!verified || verified.phone !== phone) {
      setPendingPayload(payload)
      setStep('verify')
      return
    }
    submitAppointment({ ...payload, token: verified.token })
  }

  function submitAppointment(payload: CreateAppointmentPayload) {
    createAppointment.mutate(payload, {
      onSuccess: () => {
        setConflito(null)
        setStep('success')
      },
      onError: (err) => {
        setConflito(null)
        // O número já tem sessão neste mês: avisa que ela será substituída.
        if (err instanceof ApiError && err.code === SAME_MONTH_APPOINTMENT && err.body?.existing) {
          setConflito({ payload, existing: err.body.existing, tipo: 'mesmo_mes' })
          return
        }
        // Sessão futura em outro mês: pergunta se é remarcação ou mais uma.
        if (err instanceof ApiError && err.code === OTHER_MONTH_APPOINTMENT && err.body?.existing) {
          setConflito({ payload, existing: err.body.existing, tipo: 'outro_mes' })
          return
        }
        // Token vencido: o código é refeito e o pedido repetido.
        if (err instanceof ApiError && err.status === 401) {
          setPendingPayload({ ...payload, token: undefined } as Omit<CreateAppointmentPayload, 'token'>)
          setStep('verify')
          return
        }
        // O servidor pediu cadastro que a tela não mostrou.
        if (err instanceof ApiError && err.code === CADASTRO_INCOMPLETO && Array.isArray(err.body?.faltam)) {
          setSubmitError(
            `Precisamos completar seu cadastro: ${listaDeCampos(err.body.faltam as CampoDoCadastro[])}.`
          )
          return
        }
        if (err instanceof ApiError && err.code === CPF_EM_USO) {
          setSubmitError(err.message)
          return
        }
        // Horário ocupado entre escolher e confirmar. Sem `code`: é o 409 de
        // conflito de agenda. A grade já foi invalidada (useCreateAppointment).
        if (err instanceof ApiError && err.status === 409) {
          cart.clearSchedule()
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
          <h2 className="font-display text-2xl font-bold text-ink-900">
            {remarcado ? 'Agendamento remarcado!' : 'Agendamento confirmado!'}
          </h2>
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

  const identificado = step === 'schedule' && phone
  const errorAlert = (texto: string | null) =>
    texto ? (
      <p role="alert" className="rounded-lg bg-danger-100 px-4 py-3 text-sm text-danger-500">
        {texto}
      </p>
    ) : null

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
          customer={identificado ? { nome: nomeDaPessoa, phoneLabel: formatPhoneDisplay(phone) } : null}
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
          <Button onClick={goToAreasOrPhone}>Continuar</Button>
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
            <Button disabled={pendingAreas.length > 0} onClick={() => setStep('phone')}>
              Continuar
            </Button>
          </StickyActionBar>
        </div>
      ) : null}

      {step === 'phone' ? (
        <div>
          <SectionTitle>Seu celular</SectionTitle>
          <PhoneStep
            key={phone || 'novo'}
            defaultValue={phone ? formatPhoneDisplay(phone) : ''}
            onPhoneChange={handlePhoneChange}
            onContinue={handlePhoneContinue}
            aguardando={aguardandoCadastro || cadastro.isPending}
          />
        </div>
      ) : null}

      {step === 'verify' ? (
        <div>
          <SectionTitle>Confirme seu celular</SectionTitle>
          <OtpCodeForm
            clinicId={clinicId}
            phone={phone}
            phoneLabel={formatPhoneDisplay(phone)}
            onVerified={handleVerified}
          />
        </div>
      ) : null}

      {step === 'identity' && paciente ? (
        <div>
          <SectionTitle>Confirme quem é você</SectionTitle>
          <IdentityConfirm
            nome={paciente.nome}
            faltam={paciente.faltam}
            onConfirm={handleIdentityConfirm}
            onNotMe={handleNotMe}
            submitting={cadastro.isPending}
            error={cadastroError}
          />
        </div>
      ) : null}

      {step === 'register' ? (
        <div className="flex flex-col gap-4">
          <SectionTitle>Seus dados</SectionTitle>
          <p className="text-sm text-ink-600">
            Primeira vez aqui? Precisamos do seu cadastro antes de escolher a data.
          </p>
          <CustomerInfoForm
            semCelular
            defaultValues={dadosDeCadastro ?? { fullName: cart.customerName }}
            camposFaltantes={TODOS_OS_CAMPOS}
            onSubmit={handleRegisterSubmit}
            submitting={cadastro.isPending}
            submitLabel="Continuar"
          />
          {errorAlert(cadastroError)}
        </div>
      ) : null}

      {step === 'schedule' ? (
        <div className="flex flex-col gap-6">
          {errorAlert(submitError)}
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
              loading={createAppointment.isPending}
              onClick={handleConfirmAppointment}
            >
              Confirmar agendamento
            </Button>
          </div>
          <RemarcacaoDialog
            existing={conflito?.tipo === 'mesmo_mes' ? conflito.existing : null}
            date={conflito?.payload.date ?? ''}
            time={conflito?.payload.time ?? ''}
            clinicPhone={clinic.phone}
            confirming={createAppointment.isPending}
            onConfirm={() => {
              if (!conflito) return
              setRemarcado(true)
              submitAppointment({ ...conflito.payload, substituir: true })
            }}
            onCancel={() => setConflito(null)}
          />
          <SessaoFuturaDialog
            existing={conflito?.tipo === 'outro_mes' ? conflito.existing : null}
            date={conflito?.payload.date ?? ''}
            time={conflito?.payload.time ?? ''}
            clinicPhone={clinic.phone}
            confirming={createAppointment.isPending}
            onRemarcar={() => {
              if (!conflito) return
              setRemarcado(true)
              submitAppointment({ ...conflito.payload, remarcarExistente: true })
            }}
            onMaisUma={() => {
              if (!conflito) return
              submitAppointment({ ...conflito.payload, maisUma: true })
            }}
            onCancel={() => setConflito(null)}
          />
        </div>
      ) : null}
    </div>
  )
}
