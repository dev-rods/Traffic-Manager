import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CaixaPanel } from './CaixaPanel'
import type { CaixaResumo } from '@/services/caixa.service'

const mutate = vi.fn()
const estornar = vi.fn()
const useCaixa = vi.fn()

vi.mock('@/hooks/useCaixa', () => ({
  useCaixa: (de: string, ate: string) => useCaixa(de, ate),
  useReceberDinheiro: () => ({ mutate, isPending: false }),
  useEstornar: () => ({ mutate: estornar, isPending: false }),
  useEnviarLink: () => ({ mutate: vi.fn(), isPending: false }),
}))
const showToast = vi.fn()
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))

const zero = { count: 0, cents: 0 }
const RESUMO: CaixaResumo = {
  dateFrom: '2026-10-19',
  dateTo: '2026-10-19',
  timezone: 'America/Sao_Paulo',
  totals: {
    expectedCents: 27000,
    receivedCents: 13500,
    pendingCents: 13500,
    pendingCount: 1,
    refundsPendingCents: 0,
    byMethod: {
      PIX: { count: 1, cents: 13500 },
      CREDIT_CARD: zero,
      DEBIT_CARD: zero,
      CASH: zero,
      LINK: zero,
    },
  },
  days: [
    {
      date: '2026-10-19',
      sessions: 2,
      expectedCents: 27000,
      receivedCents: 13500,
      byMethod: { PIX: 13500, CREDIT_CARD: 0, DEBIT_CARD: 0, CASH: 0, LINK: 0 },
    },
  ],
  pending: [
    {
      appointmentId: 'a2',
      date: '2026-10-19',
      startTime: '21:00',
      name: 'Rodrigo Cardoso',
      amountCents: 13500,
      checkedIn: true,
      paymentId: 'p2',
      method: 'CASH',
      paymentStatus: 'AWAITING_CASH',
    },
  ],
  payments: [
    {
      id: 'p1',
      method: 'PIX',
      amountCents: 13500,
      paidAt: '2026-10-19T12:52:00Z',
      appointmentDate: '2026-10-19',
      startTime: '10:00',
      name: 'Ana',
      simulated: true,
      appointmentCancelled: false,
    },
  ],
  refundsPending: [],
}

function secao(titulo: string): HTMLElement {
  return screen.getByRole('heading', { name: titulo }).closest('section') as HTMLElement
}

describe('CaixaPanel', () => {
  it('mostra recebido, previsto, pendências e recebimentos', async () => {
    useCaixa.mockReturnValue({ data: RESUMO, isLoading: false, isError: false })
    render(<CaixaPanel />)

    expect(screen.getByText('Recebido').nextSibling).toHaveTextContent('R$ 135,00')
    expect(screen.getByText('Previsto pelas sessões').nextSibling).toHaveTextContent('R$ 270,00')
    expect(screen.getByText('2 sessão(ões) confirmada(s)')).toBeInTheDocument()

    const pendencias = secao('Falta receber')
    expect(within(pendencias).getByText('Rodrigo Cardoso')).toBeInTheDocument()
    await userEvent.click(within(pendencias).getByRole('button', { name: 'Recebi em dinheiro' }))
    expect(mutate).toHaveBeenCalledWith('p2', expect.any(Object))

    expect(within(secao('Recebimentos')).getByText('TESTE')).toBeInTheDocument()
  })

  it('estornos pendentes: pagamento de sessão cancelada, com confirmação antes de estornar', async () => {
    const cancelado = {
      id: 'p9',
      method: 'PIX' as const,
      amountCents: 13500,
      paidAt: '2026-10-28T21:00:00Z',
      appointmentDate: '2026-10-30',
      startTime: '09:00',
      name: 'Teste Cancelado',
      simulated: true,
      appointmentCancelled: true,
    }
    useCaixa.mockReturnValue({
      data: {
        ...RESUMO,
        payments: [...RESUMO.payments, cancelado],
        refundsPending: [cancelado],
        totals: { ...RESUMO.totals, refundsPendingCents: 13500 },
      },
      isLoading: false,
      isError: false,
    })
    render(<CaixaPanel />)

    const estornos = secao('Estornos pendentes pagamentos de sessões canceladas')
    expect(within(estornos).getByText('Teste Cancelado')).toBeInTheDocument()
    await userEvent.click(within(estornos).getByRole('button', { name: 'Estornar' }))
    expect(estornar).not.toHaveBeenCalled()
    await userEvent.click(within(estornos).getByRole('button', { name: 'Confirmar estorno' }))
    expect(estornar).toHaveBeenCalledWith('p9', expect.any(Object))

    // O Asaas aceitou, mas pede a autorização do dono da conta: o aviso diz isso.
    estornar.mock.calls[0][1].onSuccess({
      id: 'p9',
      status: 'REFUNDED',
      refundNeedsAuthorization: true,
    })
    expect(showToast).toHaveBeenCalledWith({ message: expect.stringMatching(/Autorize no app/) })

    expect(within(secao('Recebimentos')).getByText('SESSÃO CANCELADA')).toBeInTheDocument()
  })

  it('sem estornos pendentes, a seção não aparece', () => {
    useCaixa.mockReturnValue({ data: RESUMO, isLoading: false, isError: false })
    render(<CaixaPanel />)
    expect(screen.queryByText('Estornos pendentes')).not.toBeInTheDocument()
  })

  it('troca o período', async () => {
    useCaixa.mockReturnValue({ data: RESUMO, isLoading: false, isError: false })
    render(<CaixaPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Últimos 7 dias' }))
    const [de, ate] = useCaixa.mock.calls[useCaixa.mock.calls.length - 1]
    expect(de < ate).toBe(true)
  })

  it('erro com tentar de novo', () => {
    useCaixa.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
      refetch: vi.fn(),
    })
    render(<CaixaPanel />)
    expect(screen.getByText('Erro ao carregar o caixa.')).toBeInTheDocument()
  })

  it('vazio ensina de onde vem o pagamento', () => {
    useCaixa.mockReturnValue({
      data: { ...RESUMO, pending: [], payments: [], totals: { ...RESUMO.totals, pendingCount: 0 } },
      isLoading: false,
      isError: false,
    })
    render(<CaixaPanel />)
    expect(screen.getByText(/aparecem aqui/)).toBeInTheDocument()
    expect(screen.getByText(/estão pagas/)).toBeInTheDocument()
  })
})
