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
  // Evento de compra
  aguardando: 0,
  aguardando_cents: 0,
  enviadas: 0,
  enviadas_cents: 0,
  retratadas: 0,
  canceladas: 0,
  ultimo_envio: null,
  // Evento de agendamento (PRD 017). Contado SEPARADO, nunca somado.
  ag_enviadas: 0,
  ag_aguardando: 0,
  ag_enviadas_cents: 0,
  ag_ultimo_envio: null,
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

    // Desde o PRD 017 a faixa tem DUAS linhas. Aqui só a de COMPRAS avisa:
    // ela tem 21 pendentes. A de agendamentos tem zero, e sem pendência não
    // há silêncio a denunciar - avisar ali seria ruído.
    expect(screen.getAllByText(/o Google ainda não recebeu/i)).toHaveLength(1)
    // Mas a DATA aparece nas duas, e vazia nas duas: nenhum dos dois subiu.
    expect(screen.getAllByText('Nenhum envio ainda')).toHaveLength(2)
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

    // Nenhuma das duas avisa: a de compras subiu, e a de agendamentos não tem
    // pendência nenhuma neste cenário.
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

  it('só mostra o valor zerado quando existe', () => {
    monta({
      totals: { total: 77, convertidos: 24, nao_convertidos: 53 },
      conversions: { ...SEM_CONVERSAO, enviadas: 20, retratadas: 3 },
    })

    // "Valor zerado", nao "Retratadas": o Google nao retrata, so troca o
    // valor - a conversao segue contando. Ver LeadsPage.tsx.
    expect(screen.getByText('Valor zerado')).toBeInTheDocument()
  })
})

/**
 * Os dois eventos de conversão aparecem SEPARADOS (risco 5.3 do PRD 017).
 *
 * A faixa lia só `uploaded_at`, do evento de compra. Com o evento de
 * agendamento, ela declararia 15 de 45 enviados - 33% - e os 10 cancelados não
 * apareceriam em nenhum dos dois números.
 *
 * Somar os dois seria pior que mostrar um: foi um total agregado que deixou a
 * `Lead - Whatsapp` morta e invisível por 6 meses, porque a `Lead jardins`
 * duplicada mantinha o número parecendo saudável. Esta faixa existe para
 * detectar silêncio - agregar derrotaria o propósito dela.
 */
describe('a faixa com os dois eventos', () => {
  const TOTAIS: LeadTotals = { total: 83, convertidos: 24, nao_convertidos: 59 }

  it('mostra uma linha para cada evento', () => {
    monta({ totals: TOTAIS, conversions: { ...SEM_CONVERSAO, enviadas: 15, ag_enviadas: 30 } })

    expect(screen.getByText('Compras')).toBeInTheDocument()
    expect(screen.getByText('Agendamentos')).toBeInTheDocument()
  })

  it('não soma os dois num número só', () => {
    // 15 compras + 30 agendamentos. "45" em qualquer lugar seria a agregação
    // que esconde um dos dois parar.
    monta({
      totals: TOTAIS,
      conversions: { ...SEM_CONVERSAO, enviadas: 15, ag_enviadas: 30 },
    })

    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
    expect(screen.queryByText('45')).not.toBeInTheDocument()
  })

  it('cada linha tem a SUA data de último envio', () => {
    // É a data que denuncia um dos dois parar: a do que morreu fica velha
    // enquanto a do outro avança. Uma data só esconderia isso.
    monta({
      totals: TOTAIS,
      conversions: {
        ...SEM_CONVERSAO,
        enviadas: 15, ultimo_envio: '2026-10-03T20:36:00Z',
        ag_enviadas: 30, ag_ultimo_envio: '2026-10-31T10:00:00Z',
      },
    })

    expect(screen.getByText(/03\/10\/2026/)).toBeInTheDocument()
    expect(screen.getByText(/31\/10\/2026/)).toBeInTheDocument()
  })

  it('avisa na linha do evento que não subiu, e só nela', () => {
    monta({
      totals: TOTAIS,
      conversions: {
        ...SEM_CONVERSAO,
        enviadas: 15, ultimo_envio: '2026-10-03T20:36:00Z',
        ag_enviadas: 0, ag_aguardando: 30,
      },
    })

    // Um aviso, não dois: a compra subiu, o agendamento não.
    expect(screen.getAllByText(/o Google ainda não recebeu/)).toHaveLength(1)
    expect(screen.getByText('Nenhum envio ainda')).toBeInTheDocument()
  })

  it('o agendamento NÃO mostra "valor zerado"', () => {
    // Este evento não retrata: quem marcou e desmarcou agendou de verdade.
    // Oferecer o número sugeriria uma correção que não existe para ele.
    monta({
      totals: TOTAIS,
      conversions: { ...SEM_CONVERSAO, enviadas: 15, retratadas: 3, ag_enviadas: 30 },
    })

    expect(screen.getAllByText('Valor zerado')).toHaveLength(1)
  })
})
