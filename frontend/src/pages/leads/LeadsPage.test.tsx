/**
 * Os contadores da tela de Leads e a camada "o Google recebeu?".
 *
 * Dois defeitos moram aqui. O primeiro: os totais eram contados sobre a página
 * carregada enquanto "Total de leads" vinha do servidor, então a taxa de
 * conversão saía de uma divisão entre conjuntos diferentes - e é o número que
 * se usa para julgar a campanha.
 *
 * O segundo é o que esta tela passa a mostrar: "Convertido" responde se a
 * pessoa agendou, não se o Google soube. Foram semanas com 24 leads
 * convertidos e zero conversões enviadas, sem nada na tela que revelasse isso.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LeadsPage } from './LeadsPage'
import type { ConversionsSummary, LeadTotals } from '@/services/leads.service'

const mockUseLeads = vi.fn()

vi.mock('@/hooks/useLeads', () => ({
  useLeads: (...args: unknown[]) => mockUseLeads(...args),
  useAcoesDoLead: () => ({
    iniciarPeloBot: { mutate: vi.fn(), isPending: false },
    alternarContatoManual: { mutate: vi.fn(), isPending: false },
  }),
}))

vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ clinicId: 'clinica-1' }) }))

const SEM_CONVERSAO: ConversionsSummary = {
  aguardando: 0,
  aguardando_cents: 0,
  enviadas: 0,
  enviadas_cents: 0,
  retratadas: 0,
  canceladas: 0,
  ultimo_envio: null,
}

function monta({
  totals,
  conversions,
}: {
  totals: LeadTotals
  conversions: ConversionsSummary | null
}) {
  mockUseLeads.mockReturnValue({
    data: { status: 'SUCCESS', leads: [], total: totals.total, totals, conversions },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })
  return render(<LeadsPage />)
}

describe('contadores de lead', () => {
  beforeEach(() => mockUseLeads.mockReset())

  it('usa os totais do servidor, não o tamanho da página', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: SEM_CONVERSAO,
    })

    expect(screen.getByText('77')).toBeInTheDocument()
    expect(screen.getByText('24')).toBeInTheDocument()
    expect(screen.getByText('53')).toBeInTheDocument()
    // 24/77, e não 24 sobre o que coube na página
    expect(screen.getByText('31%')).toBeInTheDocument()
  })

  it('não divide por zero numa clínica sem leads', () => {
    monta({
      totals: { total: 0, convertidos: 0, nao_convertidos: 0 },
      conversions: SEM_CONVERSAO,
    })

    expect(screen.getByText('0%')).toBeInTheDocument()
  })
})

describe('envio ao Google', () => {
  beforeEach(() => mockUseLeads.mockReset())

  it('avisa quando há conversão registrada que o Google não recebeu', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: { ...SEM_CONVERSAO, aguardando: 21, aguardando_cents: 544600 },
    })

    expect(screen.getByText(/o Google ainda não recebeu/i)).toBeInTheDocument()
    expect(screen.getByText('Nenhum envio ainda')).toBeInTheDocument()
    expect(screen.getByText(/R\$\s?5\.446/)).toBeInTheDocument()
  })

  it('não avisa quando já houve envio', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: {
        ...SEM_CONVERSAO,
        enviadas: 21,
        enviadas_cents: 544600,
        ultimo_envio: '2026-09-28T16:25:00+00:00',
      },
    })

    expect(screen.queryByText(/o Google ainda não recebeu/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Último envio em/)).toBeInTheDocument()
  })

  it('não avisa numa clínica que não anuncia', () => {
    monta({
      totals: { total: 12, convertidos: 3, nao_convertidos: 9 },
      conversions: SEM_CONVERSAO,
    })

    expect(screen.queryByText(/o Google ainda não recebeu/i)).not.toBeInTheDocument()
  })

  it('some inteiro quando o resumo falhou, sem derrubar a tela', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: null,
    })

    expect(screen.queryByText('Google Ads')).not.toBeInTheDocument()
    // os leads continuam sendo o trabalho: a tela segue de pé
    expect(screen.getByText('Total de leads')).toBeInTheDocument()
  })

  it('só mostra retratadas quando existem', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: { ...SEM_CONVERSAO, enviadas: 20, retratadas: 3 },
    })

    expect(screen.getByText('Retratadas')).toBeInTheDocument()
  })
})
