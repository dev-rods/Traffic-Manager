import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgendaPorData } from './AgendaPorData'
import type { AgendaSummary } from '@/services/reports.service'

const mockUseAgendaSummary = vi.fn()
vi.mock('@/hooks/useDashboard', () => ({
  useAgendaSummary: (params?: { start?: string; end?: string }) =>
    mockUseAgendaSummary(params),
}))

function dia(over: Partial<AgendaSummary['days'][number]> = {}) {
  return {
    date: '2026-09-23',
    confirmed: 4,
    cancelled: 0,
    patients: 4,
    gross_cents: 80000,
    discount_cents: 8000,
    net_cents: 72000,
    lost_cents: 0,
    booked_minutes: 90,
    avg_ticket_cents: 18000,
    cancellation_rate: 0,
    ...over,
  }
}

function resposta(days = [dia()]) {
  return {
    data: {
      status: 'SUCCESS',
      start: '2026-09-07',
      end: '2026-10-22',
      days,
      total: {
        confirmed: days.reduce((s, d) => s + d.confirmed, 0),
        cancelled: days.reduce((s, d) => s + d.cancelled, 0),
        gross_cents: days.reduce((s, d) => s + d.gross_cents, 0),
        discount_cents: days.reduce((s, d) => s + d.discount_cents, 0),
        net_cents: days.reduce((s, d) => s + d.net_cents, 0),
        lost_cents: days.reduce((s, d) => s + d.lost_cents, 0),
        booked_minutes: days.reduce((s, d) => s + d.booked_minutes, 0),
        days_with_agenda: days.length,
      },
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }
}

describe('AgendaPorData', () => {
  beforeEach(() => vi.clearAllMocks())

  // Escopado na tabela: o totalizador do periodo repete os mesmos numeros
  // quando ha um dia so, e a busca global casaria com os dois.
  it('mostra o dia com faturamento, sessões e sala ocupada', () => {
    mockUseAgendaSummary.mockReturnValue(resposta())
    render(<AgendaPorData />)

    const tabela = within(screen.getByRole('table'))
    expect(tabela.getByText(/qua, 23\/09/)).toBeInTheDocument()
    expect(tabela.getByText('R$ 720,00')).toBeInTheDocument()
    expect(tabela.getByText('1h30')).toBeInTheDocument()
  })

  // O bug que quase foi para produção: `formatCurrency` já recebe centavos e
  // divide internamente. Dividir antes mostrava R$ 7,20 no lugar de R$ 720,00.
  it('formata o dinheiro em centavos, sem dividir duas vezes', () => {
    mockUseAgendaSummary.mockReturnValue(resposta([dia({ net_cents: 72000 })]))
    render(<AgendaPorData />)

    expect(screen.queryByText('R$ 7,20')).not.toBeInTheDocument()
  })

  it('cancelamento aparece com a perda em reais junto', () => {
    mockUseAgendaSummary.mockReturnValue(
      resposta([dia({ cancelled: 2, lost_cents: 30000, cancellation_rate: 33 })]),
    )
    render(<AgendaPorData />)

    const tabela = within(screen.getByRole('table'))
    expect(tabela.getByText('- R$ 300,00')).toBeInTheDocument()
    expect(tabela.getByText('2')).toBeInTheDocument()
  })

  it('dia sem desconto e sem cancelamento não polui a linha', () => {
    mockUseAgendaSummary.mockReturnValue(resposta([dia({ discount_cents: 0 })]))
    render(<AgendaPorData />)

    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  it('começa olhando para a frente', () => {
    mockUseAgendaSummary.mockReturnValue(resposta())
    render(<AgendaPorData />)

    const hoje = new Date().toISOString().slice(0, 10)
    expect(mockUseAgendaSummary).toHaveBeenCalledWith(
      expect.objectContaining({ start: hoje }),
    )
  })

  it('dá para ver datas passadas', async () => {
    mockUseAgendaSummary.mockReturnValue(resposta())
    render(<AgendaPorData />)

    await userEvent.click(screen.getByRole('button', { name: 'Já passou' }))

    const hoje = new Date().toISOString().slice(0, 10)
    const chamadas = mockUseAgendaSummary.mock.calls
    const ultima = chamadas[chamadas.length - 1][0]
    expect(ultima.end < hoje).toBe(true)
  })

  it('trata carregando', () => {
    mockUseAgendaSummary.mockReturnValue({ isLoading: true, isError: false, refetch: vi.fn() })
    render(<AgendaPorData />)

    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('trata erro com retry', () => {
    const refetch = vi.fn()
    mockUseAgendaSummary.mockReturnValue({
      isLoading: false, isError: true, error: new Error('caiu'), refetch,
    })
    render(<AgendaPorData />)

    expect(screen.getByText('caiu')).toBeInTheDocument()
  })

  it('trata período sem agenda', () => {
    mockUseAgendaSummary.mockReturnValue(resposta([]))
    render(<AgendaPorData />)

    expect(screen.getByText('Nenhum dia com agendamento')).toBeInTheDocument()
  })
})
