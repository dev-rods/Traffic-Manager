import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DocumentosPage } from './DocumentosPage'
import { checkinService } from '@/services/checkin.service'
import { ApiError } from '@/services/api'
import type { AnamneseCatalogo, CheckinAppointment, Consent, ConsentPrefill } from '@/types'

vi.mock('@/services/checkin.service')

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

const ANA: CheckinAppointment = {
  id: 'ap-ana',
  date: '2026-12-03',
  startTime: '10:00',
  fullName: 'Ana Souza',
  serviceName: 'Depilação a Laser',
  areas: ['Axilas', 'Buço'],
  originalPriceCents: 25000,
  finalPriceCents: 22500,
  discountPct: 10,
  checkedInAt: null,
  payment: null,
  consentRequired: true,
  consentPrefill: PREFILL,
}

// Uma tela só, uma pergunta Sim/Não: o bastante para a ficha passar pelo fluxo.
const CATALOGO: AnamneseCatalogo = {
  version: '03',
  phototypes: [{ value: 'III', text: 'Pele clara média' }],
  screens: [
    {
      n: 1,
      questions: [
        {
          key: 'gestante',
          text: 'Está gestante?',
          type: 'SIM_NAO',
          conditionalOf: null,
          label: null,
          required: true,
          section: '2. Histórico médico',
        },
      ],
    },
  ],
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

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/c1/documentos']}>
        <Routes>
          <Route path="/:clinicId/documentos" element={<DocumentosPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function login() {
  await userEvent.type(await screen.findByLabelText('Celular (WhatsApp)'), '11999990000')
  await userEvent.click(screen.getByRole('button', { name: 'Receber código' }))
  await screen.findByText('Digite o código')
  await userEvent.type(screen.getByLabelText('Código de 6 dígitos'), '123456')
}

beforeEach(() => {
  vi.mocked(checkinService.bootstrap).mockResolvedValue({
    clinic: { clinic_id: 'c1', name: 'Clínica X', display_name: 'Essência', logo_url: null },
    anamnesis: CATALOGO,
  })
  vi.mocked(checkinService.sendCode).mockResolvedValue(null)
  vi.mocked(checkinService.confirmCode).mockResolvedValue('tok-doc')
  vi.mocked(checkinService.appointments).mockResolvedValue([ANA])
  vi.mocked(checkinService.saveAnamnesis).mockResolvedValue({
    screen: 1,
    answered: ['gestante'],
    complete: true,
  })
  vi.mocked(checkinService.startConsent).mockResolvedValue(consent())
  vi.mocked(checkinService.consent).mockResolvedValue(consent())
  vi.mocked(checkinService.simulateConsent).mockResolvedValue(consent({ status: 'SIGNED' }))
})

describe('Documentos pelo celular (PRD 048)', () => {
  it('entra com o código de escopo documentos, responde a ficha retomando o que havia, assina e termina sem pagar', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([
      { ...ANA, anamnesisAnswers: { gestante: true } },
    ])
    renderPage()
    await login()
    expect(checkinService.confirmCode).toHaveBeenCalledWith('c1', '5511999990000', '123456', 'documentos')

    await screen.findByText('Olá, Ana')
    expect(screen.getByText(/Quinta, 3 de dezembro/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Começar' }))

    // Dados conferidos (já preenchidos): segue.
    expect(
      await screen.findByRole('heading', { name: 'Termo de consentimento' })
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Nome completo')).toHaveValue('Ana Souza')
    await userEvent.click(screen.getByRole('radio', { name: 'Autorizo' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continuar para a ficha de anamnese' })
    )

    // A ficha abre com a resposta que já estava gravada.
    expect(await screen.findByRole('heading', { name: 'Ficha de anamnese' })).toBeInTheDocument()
    const gestante = screen.getByRole('radiogroup', { name: 'Está gestante?' })
    expect(within(gestante).getByRole('radio', { name: 'Sim' })).toHaveAttribute(
      'aria-checked',
      'true'
    )
    await userEvent.click(screen.getByRole('button', { name: 'Continuar para a assinatura' }))
    expect(checkinService.saveAnamnesis).toHaveBeenCalledWith(
      'c1',
      { phone: '5511999990000', token: 'tok-doc' },
      'ap-ana',
      1,
      { gestante: true }
    )

    // Preparar e assinar (provedor simulado).
    expect(await screen.findByRole('heading', { name: 'Assine o termo' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Simular assinatura (teste)' }))
    await screen.findByText('Tudo certo, Ana!')
    expect(screen.getByText(/Documento assinado/)).toBeInTheDocument()
    expect(screen.getByText('Pode fechar esta página.')).toBeInTheDocument()
    expect(checkinService.confirm).not.toHaveBeenCalled()
    expect(checkinService.pay).not.toHaveBeenCalled()
  })

  it('sem sessão com documento pendente: nada a fazer', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([{ ...ANA, consentRequired: false }])
    renderPage()
    await login()
    await screen.findByText('Tudo certo, Ana')
    expect(screen.getByText(/Não há nada para preencher agora/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Começar' })).not.toBeInTheDocument()
  })

  it('número sem sessão: "não encontramos", nunca "tudo certo" (PRD 063)', async () => {
    vi.mocked(checkinService.appointments).mockResolvedValue([])
    renderPage()
    await login()
    await screen.findByText('Não encontramos sessão para este número')
    expect(screen.getByText(/Confira o celular digitado/)).toBeInTheDocument()
    expect(screen.queryByText(/Tudo certo/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Entrar de novo' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Tentar outro número' }))
    expect(await screen.findByLabelText('Celular (WhatsApp)')).toBeInTheDocument()
  })

  it('número de fora do Brasil: escolhe o país e pede o código (25/11/2026)', async () => {
    renderPage()
    const pais = await screen.findByLabelText('País')
    expect(pais).toHaveValue('55')
    await userEvent.selectOptions(pais, '1')
    const campo = screen.getByLabelText('Celular (WhatsApp)')
    await userEvent.type(campo, '(818) 472-2644')
    expect(campo).toHaveValue('8184722644')
    await userEvent.click(screen.getByRole('button', { name: 'Receber código' }))
    expect(checkinService.sendCode).toHaveBeenCalledWith('c1', '+18184722644')
    expect(await screen.findByText('Digite o código')).toBeInTheDocument()
  })

  it('"Outro país" pede o código do país à mão', async () => {
    renderPage()
    await userEvent.selectOptions(await screen.findByLabelText('País'), 'outro')
    await userEvent.type(screen.getByLabelText('Código do país'), '45')
    await userEvent.type(screen.getByLabelText('Celular (WhatsApp)'), '12345678')
    await userEvent.click(screen.getByRole('button', { name: 'Receber código' }))
    expect(checkinService.sendCode).toHaveBeenCalledWith('c1', '+4512345678')
  })

  it('Brasil continua exigindo celular com nono dígito', async () => {
    renderPage()
    await userEvent.type(await screen.findByLabelText('Celular (WhatsApp)'), '1133334444')
    expect(screen.getByRole('button', { name: 'Receber código' })).toBeDisabled()
  })

  it('token vencido volta ao telefone com o aviso', async () => {
    vi.mocked(checkinService.appointments).mockRejectedValue(
      new ApiError('Sua sessão expirou. Confirme o código de novo.', 401)
    )
    renderPage()
    await login()
    await screen.findByText(/Sua sessão venceu/)
    expect(screen.getByLabelText('Celular (WhatsApp)')).toBeInTheDocument()
  })
})
