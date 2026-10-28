import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CheckinPage } from './CheckinPage'
import { checkinService } from '@/services/checkin.service'
import { ApiError } from '@/services/api'
import type { CheckinAppointment, Payment } from '@/types'

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
  })
  vi.mocked(checkinService.sendCode).mockResolvedValue(null)
  vi.mocked(checkinService.confirmCode).mockResolvedValue('tok')
  vi.mocked(checkinService.appointments).mockResolvedValue([ANA])
  vi.mocked(checkinService.confirm).mockResolvedValue({ payerCpfKnown: true })
  vi.mocked(checkinService.pay).mockResolvedValue(payment())
  vi.mocked(checkinService.payment).mockResolvedValue(payment())
  vi.mocked(checkinService.simulate).mockResolvedValue(payment({ status: 'PAID' }))
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

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
    vi.mocked(checkinService.confirm).mockResolvedValue({ payerCpfKnown: false })
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
    await userEvent.click(await screen.findByRole('button', { name: 'Está certo, confirmar' }))
    expect(await screen.findByText(/Seu pagamento está confirmado/)).toBeInTheDocument()
    expect(checkinService.pay).not.toHaveBeenCalled()
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

  it('"Recomeçar" volta ao início a qualquer momento', async () => {
    renderPage()
    await login()
    await screen.findByRole('heading', { name: 'Olá, Ana!' })
    await userEvent.click(screen.getByRole('button', { name: 'Recomeçar' }))
    expect(await screen.findByRole('button', { name: 'Fazer check-in' })).toBeInTheDocument()
  })
})
