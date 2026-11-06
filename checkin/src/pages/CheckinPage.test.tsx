import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CheckinPage } from './CheckinPage'
import { checkinService } from '@/services/checkin.service'
import { ApiError } from '@/services/api'
import type {
  AnamneseCatalogo,
  CheckinAppointment,
  Consent,
  ConsentPrefill,
  Payment,
} from '@/types'

vi.mock('@/services/checkin.service')

const today = new Date()
const TODAY = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

const ANA: CheckinAppointment = {
  id: 'ap-ana',
  date: TODAY,
  startTime: '10:00',
  fullName: 'Ana Souza',
  serviceName: 'Depilação a Laser',
  areas: ['Axilas', 'Buço'],
  originalPriceCents: 25000,
  finalPriceCents: 22500,
  discountPct: 10,
  checkedInAt: null,
  payment: null,
  consentRequired: false,
  consentPrefill: null,
}
const BIA: CheckinAppointment = { ...ANA, id: 'ap-bia', fullName: 'Bia Souza', startTime: '11:00' }

function payment(over: Partial<Payment> = {}): Payment {
  return {
    id: 'pay-1',
    method: 'PIX',
    status: 'PENDING',
    amountCents: 22500,
    invoiceUrl: null,
    pixPayload: '000201PIX',
    paidAt: null,
    simulated: true,
    canSimulate: true,
    ...over,
  }
}

const PREFILL: ConsentPrefill = {
  name: 'Ana Souza',
  cpfMasked: '***.***.***-25',
  cpfKnown: true,
  birthDate: '1990-05-10',
  phone: '5511999990000',
  email: 'ana@exemplo.com',
  isMinor: false,
  clinicReady: true,
  guardian: null,
}

function consent(over: Partial<Consent> = {}): Consent {
  return {
    id: 'cons-1',
    status: 'SIGNING',
    signerId: 'sim-signer-1',
    widgetEndpoint: '',
    test: true,
    canSimulate: true,
    signedAt: null,
    ...over,
  }
}

function withConsent(prefill: Partial<ConsentPrefill> = {}) {
  // O termo vem antes da conferência: quem diz "precisa assinar" é a lista.
  vi.mocked(checkinService.appointments).mockResolvedValue([
    { ...ANA, consentRequired: true, consentPrefill: { ...PREFILL, ...prefill } },
  ])
  vi.mocked(checkinService.confirm).mockResolvedValue({
    payerCpfKnown: true,
    consentRequired: false,
    consentPrefill: null,
  })
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/c1']}>
        <Routes>
          <Route path="/:clinicId" element={<CheckinPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function typeDigits(digits: string) {
  for (const d of digits) await userEvent.click(screen.getByRole('button', { name: d }))
}

async function login() {
  await userEvent.click(await screen.findByRole('button', { name: 'Fazer check-in' }))
  await typeDigits('11999990000')
  await userEvent.click(screen.getByRole('button', { name: 'Receber código' }))
  await screen.findByText('Digite o código')
  await typeDigits('123456')
}

beforeEach(() => {
  vi.mocked(checkinService.bootstrap).mockResolvedValue({
    clinic: { clinic_id: 'c1', name: 'Clínica X', display_name: 'Essência', logo_url: null },
    anamnesis: null,
  })
  vi.mocked(checkinService.saveAnamnesis).mockResolvedValue({
    screen: 1,
    answered: [],
    complete: false,
  })
  vi.mocked(checkinService.sendCode).mockResolvedValue(null)
  vi.mocked(checkinService.confirmCode).mockResolvedValue('tok')
  vi.mocked(checkinService.appointments).mockResolvedValue([ANA])
  vi.mocked(checkinService.confirm).mockResolvedValue({
    payerCpfKnown: true,
    consentRequired: false,
    consentPrefill: null,
  })
  vi.mocked(checkinService.startConsent).mockResolvedValue(consent())
  vi.mocked(checkinService.consent).mockResolvedValue(consent())
  vi.mocked(checkinService.simulateConsent).mockResolvedValue(consent({ status: 'SIGNED' }))
  vi.mocked(checkinService.pay).mockResolvedValue(payment())
  vi.mocked(checkinService.payment).mockResolvedValue(payment())
  vi.mocked(checkinService.simulate).mockResolvedValue(payment({ status: 'PAID' }))
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

// Catálogo curto da ficha (PRD 038): 2 telas em vez de 4, mesmo formato do backend.
const CATALOGO: AnamneseCatalogo = {
  version: '03',
  phototypes: [
    { value: 'I', text: 'Pele muito clara' },
    { value: 'III', text: 'Pele clara média' },
  ],
  screens: [
    {
      n: 1,
      questions: [
        {
          key: 'queixa_principal',
          text: 'O que motivou a busca?',
          type: 'TEXTO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '1. Queixa principal',
        },
        {
          key: 'gestante',
          text: 'Está gestante?',
          type: 'SIM_NAO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '2. Histórico médico',
        },
        {
          key: 'hormonal',
          text: 'Possui distúrbios hormonais?',
          type: 'SIM_NAO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '2. Histórico médico',
        },
        {
          key: 'hormonal_quais',
          text: 'Quais?',
          type: 'TEXTO',
          conditionalOf: 'hormonal',
          label: 'Se sim, quais?',
          required: true,
          section: '2. Histórico médico',
        },
      ],
    },
    {
      n: 2,
      questions: [
        {
          key: 'fuma',
          text: 'Fuma?',
          type: 'SIM_NAO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '5. Hábitos',
        },
        {
          key: 'observacoes',
          text: 'Observações',
          type: 'TEXTO',
          conditionalOf: null,
          label: null,
          required: false,
          section: '7. Observações',
        },
        {
          key: 'fototipo',
          text: 'Como sua pele reage ao sol?',
          type: 'FOTOTIPO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '8. Fototipo',
        },
      ],
    },
  ],
}

function comFicha() {
  vi.mocked(checkinService.bootstrap).mockResolvedValue({
    clinic: { clinic_id: 'c1', name: 'Clínica X', display_name: 'Essência', logo_url: null },
    anamnesis: CATALOGO,
  })
  withConsent()
}

async function ateADadosConfirmados() {
  renderPage()
  await login()
  await screen.findByRole('heading', { name: 'Termo de consentimento' })
  await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
  await userEvent.click(screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' }))
  await screen.findByRole('heading', { name: 'Ficha de anamnese' })
}

describe('Check-in', () => {
  it('fluxo do Pix: login, confirma, paga e conclui', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Essência' })).toBeInTheDocument()
    await login()

    expect(await screen.findByRole('heading', { name: 'Olá, Ana!' })).toBeInTheDocument()
    expect(screen.getByText('R$ 225,00')).toBeInTheDocument()
    expect(checkinService.sendCode).toHaveBeenCalledWith('c1', '5511999990000')
    expect(checkinService.confirmCode).toHaveBeenCalledWith('c1', '5511999990000', '123456')

    await userEvent.click(screen.getByRole('button', { name: 'Está certo, confirmar' }))
    expect(checkinService.confirm).toHaveBeenCalledWith(
      'c1',
      { phone: '5511999990000', token: 'tok' },
      'ap-ana'
    )

    await userEvent.click(await screen.findByRole('button', { name: /^Pix/ }))
    expect(checkinService.pay).toHaveBeenCalledWith(
      'c1',
      { phone: '5511999990000', token: 'tok' },
      'ap-ana',
      'PIX',
      undefined
    )
    expect(await screen.findByRole('img', { name: 'QR code do Pix' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Simular pagamento (teste)' }))
    expect(await screen.findByRole('heading', { name: 'Tudo certo, Ana!' })).toBeInTheDocument()
  })

  it('confirma sozinho quando o pagamento entra', async () => {
    vi.mocked(checkinService.payment).mockResolvedValue(payment({ status: 'PAID' }))
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Pix/ }))
    expect(await screen.findByRole('heading', { name: 'Tudo certo, Ana!' })).toBeInTheDocument()
  })

  it('telefone de duas pessoas: escolhe qual agendamento', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([ANA, BIA])
    renderPage()
    await login()
    expect(await screen.findByText('Qual é o seu agendamento?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Bia Souza/ }))
    expect(await screen.findByRole('heading', { name: 'Olá, Bia!' })).toBeInTheDocument()
  })

  it('sem CPF conhecido: pede, valida e usa nas próximas tentativas', async () => {
    vi.mocked(checkinService.confirm).mockResolvedValue({
      payerCpfKnown: false,
      consentRequired: false,
      consentPrefill: null,
    })
    const card = payment({
      method: 'CREDIT_CARD',
      pixPayload: null,
      invoiceUrl: 'https://asaas/i/1',
    })
    vi.mocked(checkinService.pay).mockResolvedValue(card)
    vi.mocked(checkinService.payment).mockResolvedValue(card)
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Crédito/ }))

    expect(await screen.findByText('Qual é o seu CPF?')).toBeInTheDocument()
    await typeDigits('52998224724')
    expect(screen.getByRole('alert')).toHaveTextContent('Confira o CPF')
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))
    await typeDigits('5')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(checkinService.pay).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      'CREDIT_CARD',
      '52998224725'
    )
    expect(await screen.findByRole('img', { name: 'QR code da fatura' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Trocar forma de pagamento' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Pix/ }))
    expect(checkinService.pay).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      'PIX',
      '52998224725'
    )
  })

  it('Asaas sandbox: cartão mostra o cartão de teste, sem botão de simular', async () => {
    const card = payment({
      method: 'CREDIT_CARD',
      pixPayload: null,
      invoiceUrl: 'https://sandbox.asaas.com/i/1',
      canSimulate: false,
    })
    vi.mocked(checkinService.pay).mockResolvedValue(card)
    vi.mocked(checkinService.payment).mockResolvedValue(card)
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Crédito/ }))

    expect(await screen.findByRole('img', { name: 'QR code da fatura' })).toBeInTheDocument()
    expect(screen.getByText('4444 4444 4444 4444')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Simular pagamento (teste)' })).toBeNull()
  })

  it('produção: sem cartão de teste nem botão de simular', async () => {
    const card = payment({
      method: 'CREDIT_CARD',
      pixPayload: null,
      invoiceUrl: 'https://www.asaas.com/i/1',
      simulated: false,
      canSimulate: false,
    })
    vi.mocked(checkinService.pay).mockResolvedValue(card)
    vi.mocked(checkinService.payment).mockResolvedValue(card)
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Crédito/ }))

    expect(await screen.findByRole('img', { name: 'QR code da fatura' })).toBeInTheDocument()
    expect(screen.queryByText('4444 4444 4444 4444')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Simular pagamento (teste)' })).toBeNull()
  })

  it('dinheiro: termina o check-in e manda para a recepção', async () => {
    vi.mocked(checkinService.pay).mockResolvedValue(
      payment({ method: 'CASH', status: 'AWAITING_CASH', pixPayload: null })
    )
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Dinheiro/ }))
    expect(
      await screen.findByText('Check-in feito. Pague R$ 225,00 em dinheiro na recepção.')
    ).toBeInTheDocument()
  })

  it('já pago: não cobra de novo', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([
      { ...ANA, payment: payment({ status: 'PAID' }) },
    ])
    renderPage()
    await login()
    // Sem pedir "confirmar" de novo: no teste gravado isso pareceu um duplo
    // check-in (PRD 028, M1).
    expect(await screen.findByText(/Seu pagamento já está confirmado/)).toBeInTheDocument()
    expect(checkinService.confirm).not.toHaveBeenCalled()
    expect(checkinService.pay).not.toHaveBeenCalled()
  })

  it('link pendente mandado pela recepção: mostra a mesma fatura (PRD 029)', async () => {
    const link = payment({ method: 'LINK', pixPayload: null, invoiceUrl: 'https://asaas/i/link' })
    vi.mocked(checkinService.appointments).mockResolvedValue([{ ...ANA, payment: link }])
    vi.mocked(checkinService.payment).mockResolvedValue(link)
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    expect(await screen.findByText(/mesmo link que enviamos no seu WhatsApp/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trocar forma de pagamento' })).toBeInTheDocument()
    expect(checkinService.pay).not.toHaveBeenCalled()
  })

  it('a lista mostra o que já foi feito em cada agendamento', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([
      { ...ANA, payment: payment({ status: 'PAID', method: 'PIX' }) },
      { ...BIA, checkedInAt: '2026-10-28T22:06:00Z' },
    ])
    renderPage()
    await login()
    expect(await screen.findByText('Pago · Pix')).toBeInTheDocument()
    expect(screen.getByText(/^Check-in às/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Bia Souza/ }))
    expect(await screen.findByText(/Seu check-in já foi feito às/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar para o pagamento' })).toBeInTheDocument()
  })

  it('escolher na lista o agendamento já pago vai direto para a confirmação', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([
      { ...ANA, payment: payment({ status: 'PAID' }) },
      BIA,
    ])
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: /Ana Souza/ }))
    expect(await screen.findByText(/Seu pagamento já está confirmado/)).toBeInTheDocument()
    expect(checkinService.confirm).not.toHaveBeenCalled()
  })

  it('cartão em teste mostra todos os dados da fatura', async () => {
    const card = payment({
      method: 'CREDIT_CARD',
      pixPayload: null,
      invoiceUrl: 'https://asaas/i/1',
      canSimulate: false,
    })
    vi.mocked(checkinService.pay).mockResolvedValue(card)
    vi.mocked(checkinService.payment).mockResolvedValue(card)
    renderPage()
    await login()
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    await userEvent.click(await screen.findByRole('button', { name: /^Crédito/ }))
    expect(await screen.findByText('Ambiente de teste: dados para a fatura')).toBeInTheDocument()
    expect(screen.getByText('qualquer nome')).toBeInTheDocument()
    expect(screen.getByText('529.982.247-25')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Simular pagamento (teste)' })
    ).not.toBeInTheDocument()
  })

  it('número sem agendamento', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([])
    renderPage()
    await login()
    expect(await screen.findByText('Não encontramos seu agendamento')).toBeInTheDocument()
  })

  it('código errado: mostra o erro e limpa os dígitos', async () => {
    vi.mocked(checkinService.confirmCode).mockRejectedValue(new ApiError('Código inválido', 400))
    renderPage()
    await login()
    expect(await screen.findByRole('alert')).toHaveTextContent('Código inválido')
    const boxes = within(screen.getByLabelText('Código digitado')).getAllByText('', {
      selector: 'span',
    })
    expect(boxes.every((b) => b.textContent === '')).toBe(true)
  })

  it('sem toque por 90 s volta ao início', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Olá, Ana!' })
    await act(async () => {
      vi.advanceTimersByTime(91_000)
    })
    expect(await screen.findByRole('button', { name: 'Fazer check-in' })).toBeInTheDocument()
    expect(screen.queryByText('Ana Souza')).not.toBeInTheDocument()
  })

  it('dev sem WhatsApp: mostra o código de teste na tela', async () => {
    vi.mocked(checkinService.sendCode).mockResolvedValue('654321')
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Fazer check-in' }))
    await typeDigits('11999990000')
    await userEvent.click(screen.getByRole('button', { name: 'Receber código' }))
    expect(await screen.findByText(/Ambiente de teste/)).toHaveTextContent('654321')
  })

  it('termo exigido: confere os dados, simula a assinatura e só então paga (PRD 036)', async () => {
    withConsent()
    renderPage()
    await login()

    expect(
      await screen.findByRole('heading', { name: 'Termo de consentimento' })
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Pix/ })).toBeNull()
    expect(screen.getByLabelText('Nome completo')).toHaveValue('Ana Souza')
    expect(screen.getByText('***.***.***-25')).toBeInTheDocument()
    expect(screen.getByLabelText('Data de nascimento')).toHaveValue('10/05/1990')
    expect(screen.getByLabelText('E-mail')).toHaveValue('ana@exemplo.com')

    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(checkinService.startConsent).toHaveBeenCalledWith(
      'c1',
      { phone: '5511999990000', token: 'tok' },
      'ap-ana',
      {
        fullName: 'Ana Souza',
        cpf: null,
        birthDate: '1990-05-10',
        email: 'ana@exemplo.com',
        imageAuthorized: true,
        guardian: null,
      }
    )

    expect(await screen.findByRole('heading', { name: 'Assine o termo' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Simular assinatura (teste)' }))
    expect(checkinService.simulateConsent).toHaveBeenCalledWith('c1', expect.anything(), 'cons-1')
    // Depois de assinar, a conferência do agendamento; só então o pagamento.
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    expect(await screen.findByRole('button', { name: /^Pix/ })).toBeInTheDocument()
  })

  it('termo: dados obrigatórios e CPF digitado quando não é o conhecido', async () => {
    withConsent({ cpfKnown: false, cpfMasked: null, birthDate: null, email: null })
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })

    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(checkinService.startConsent).not.toHaveBeenCalled()
    expect(screen.getByText('Informe o CPF.')).toBeInTheDocument()
    expect(screen.getByText('Informe a data de nascimento.')).toBeInTheDocument()
    expect(screen.getByText('Informe um e-mail válido.')).toBeInTheDocument()
    expect(screen.getByText('Escolha uma das opções.')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('CPF'), '52998224725')
    await userEvent.type(screen.getByLabelText('Data de nascimento'), '10051990')
    await userEvent.type(screen.getByLabelText('E-mail'), 'ana@exemplo.com')
    await userEvent.click(screen.getByRole('radio', { name: 'Não autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(checkinService.startConsent).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      expect.objectContaining({
        cpf: '52998224725',
        birthDate: '1990-05-10',
        imageAuthorized: false,
      })
    )
  })

  it('termo: menor de idade exige o responsável, que é quem assina', async () => {
    withConsent({ name: 'Bia Souza', birthDate: '2010-06-01', isMinor: true })
    renderPage()
    await login()
    expect(await screen.findByRole('heading', { name: 'Responsável legal' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(checkinService.startConsent).not.toHaveBeenCalled()

    await userEvent.type(screen.getByLabelText('Nome completo do responsável'), 'Carla Souza')
    await userEvent.type(screen.getByLabelText('CPF do responsável'), '11144477735')
    await userEvent.type(screen.getByLabelText('Nascimento do responsável'), '01011980')
    await userEvent.type(screen.getByLabelText('Celular do responsável'), '11988887777')
    await userEvent.type(screen.getByLabelText('E-mail do responsável'), 'carla@exemplo.com')
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(checkinService.startConsent).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      expect.objectContaining({
        guardian: {
          name: 'Carla Souza',
          cpf: '11144477735',
          birthDate: '1980-01-01',
          phone: '5511988887777',
          email: 'carla@exemplo.com',
        },
      })
    )
  })

  it('termo: clínica sem responsável cadastrada manda chamar a recepção', async () => {
    withConsent({ clinicReady: false })
    renderPage()
    await login()
    expect(await screen.findByText(/A clínica ainda não configurou o termo/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Pix/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Continuar para a ficha de anamnese' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar ao início' }))
    expect(await screen.findByRole('button', { name: 'Fazer check-in' })).toBeInTheDocument()
  })

  it('termo: erro do servidor aparece na tela', async () => {
    withConsent()
    vi.mocked(checkinService.startConsent).mockRejectedValue(
      new ApiError('Confira o CPF da paciente: os números não batem.', 400)
    )
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Confira o CPF da paciente')
  })

  it('termo já resolvido (NOT_REQUIRED) segue direto para o pagamento', async () => {
    withConsent()
    vi.mocked(checkinService.startConsent).mockResolvedValue(
      consent({ id: null, status: 'NOT_REQUIRED' })
    )
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    // Depois de assinar, a conferência do agendamento; só então o pagamento.
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    expect(await screen.findByRole('button', { name: /^Pix/ })).toBeInTheDocument()
  })

  it('termo: a assinatura confirmada pelo polling segue sozinha', async () => {
    withConsent()
    vi.mocked(checkinService.startConsent).mockResolvedValue(
      consent({ canSimulate: false, widgetEndpoint: 'https://sandbox.clicksign.com' })
    )
    vi.mocked(checkinService.consent).mockResolvedValue(
      consent({ status: 'SIGNED', canSimulate: false })
    )
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    // Depois de assinar, a conferência do agendamento; só então o pagamento.
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    expect(await screen.findByRole('button', { name: /^Pix/ })).toBeInTheDocument()
  })

  it('termo: o widget tem altura definida e abre em tela cheia sem remontar (PRD 036)', async () => {
    withConsent()
    vi.mocked(checkinService.startConsent).mockResolvedValue(
      consent({ canSimulate: false, widgetEndpoint: 'https://sandbox.clicksign.com' })
    )
    vi.mocked(checkinService.consent).mockResolvedValue(consent({ canSimulate: false }))
    const mount = vi.fn()
    const unmount = vi.fn()
    window.Clicksign = class {
      endpoint = ''
      origin = ''
      mount = mount
      unmount = unmount
      on = vi.fn()
    }
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    await screen.findByRole('heading', { name: 'Assine o termo' })

    // O iframe da ClickSign tem height: 100%: o container ocupa o que sobra
    // da tela (item flex de um pai com altura definida).
    const container = screen.getByTestId('clicksign-widget')
    expect(mount).toHaveBeenCalledWith('clicksign-widget')
    expect(container.className).toContain('flex-1')

    await userEvent.click(screen.getByRole('button', { name: 'Tela cheia' }))
    expect(screen.getByTestId('clicksign-frame').className).toContain('fixed inset-0')
    expect(unmount).not.toHaveBeenCalled()
    expect(mount).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Reduzir' }))
    expect(screen.getByTestId('clicksign-frame').className).not.toContain('fixed')
    delete window.Clicksign
  })

  it('ficha de anamnese: 4 telas viram 2 aqui, condicional só com "Sim", grava por tela e assina (PRD 038)', async () => {
    comFicha()
    await ateADadosConfirmados()
    expect(screen.getByText(/Tela 1 de 2/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Se sim, quais?')).toBeNull()

    // Sem default: continuar sem responder marca as perguntas.
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(checkinService.saveAnamnesis).not.toHaveBeenCalled()
    expect(screen.getAllByText('Responda Sim ou Não.')).toHaveLength(2)

    await userEvent.type(screen.getByLabelText('O que motivou a busca?'), 'Pelos encravados')
    const gestante = screen.getByRole('radiogroup', { name: 'Está gestante?' })
    await userEvent.click(within(gestante).getByRole('radio', { name: 'Não' }))
    const hormonal = screen.getByRole('radiogroup', { name: 'Possui distúrbios hormonais?' })
    await userEvent.click(within(hormonal).getByRole('radio', { name: 'Sim' }))
    expect(screen.getByLabelText('Se sim, quais?')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Se sim, quais?'), 'SOP')
    // Mudou de ideia: a condicional some e não vai no envio.
    await userEvent.click(within(hormonal).getByRole('radio', { name: 'Não' }))
    expect(screen.queryByLabelText('Se sim, quais?')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(checkinService.saveAnamnesis).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      1,
      {
        queixa_principal: 'Pelos encravados',
        gestante: false,
        hormonal: false,
      }
    )

    expect(await screen.findByText(/Tela 2 de 2/)).toBeInTheDocument()
    const fuma = screen.getByRole('radiogroup', { name: 'Fuma?' })
    await userEvent.click(within(fuma).getByRole('radio', { name: 'Não' }))
    await userEvent.click(screen.getByRole('radio', { name: /III/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continuar para a assinatura' }))
    expect(checkinService.saveAnamnesis).toHaveBeenLastCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      2,
      {
        fuma: false,
        fototipo: 'III',
      }
    )

    // Só então o envelope, com os dados conferidos na tela de dados.
    expect(await screen.findByRole('heading', { name: 'Assine o termo' })).toBeInTheDocument()
    expect(checkinService.startConsent).toHaveBeenCalledWith(
      'c1',
      expect.anything(),
      'ap-ana',
      expect.objectContaining({ fullName: 'Ana Souza', imageAuthorized: true })
    )
  })

  it('ficha: nada vem pré-assinalado, nem "Não"; "Voltar" na tela 1 volta aos dados', async () => {
    comFicha()
    await ateADadosConfirmados()
    expect(screen.getByLabelText('O que motivou a busca?')).toHaveValue('')
    for (const radio of screen.getAllByRole('radio')) expect(radio).not.toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(
      await screen.findByRole('heading', { name: 'Termo de consentimento' })
    ).toBeInTheDocument()
  })

  it('ficha: erro 400 do backend marca o campo e não avança', async () => {
    comFicha()
    vi.mocked(checkinService.saveAnamnesis).mockRejectedValue(
      new ApiError('Responda esta pergunta.', 400, 'gestante')
    )
    await ateADadosConfirmados()
    await userEvent.type(screen.getByLabelText('O que motivou a busca?'), 'Virilha')
    for (const nome of ['Está gestante?', 'Possui distúrbios hormonais?']) {
      await userEvent.click(
        within(screen.getByRole('radiogroup', { name: nome })).getByRole('radio', { name: 'Não' })
      )
    }
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('Confira esta resposta.')).toBeInTheDocument()
    expect(screen.getByText(/Tela 1 de 2/)).toBeInTheDocument()
    expect(checkinService.startConsent).not.toHaveBeenCalled()
  })

  it('sem catálogo no bootstrap (termo desligado) o fluxo é o de antes: dados e assinatura', async () => {
    withConsent()
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Termo de consentimento' })
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )
    expect(await screen.findByRole('heading', { name: 'Assine o termo' })).toBeInTheDocument()
    expect(checkinService.saveAnamnesis).not.toHaveBeenCalled()
  })

  it('"Recomeçar" volta ao início a qualquer momento', async () => {
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Olá, Ana!' })
    await userEvent.click(screen.getByRole('button', { name: 'Recomeçar' }))
    expect(await screen.findByRole('button', { name: 'Fazer check-in' })).toBeInTheDocument()
  })
})
