import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CrmPage } from './CrmPage'
import type { Lead } from '@/types'

const mockUseLeads = vi.fn()
const mockMutate = vi.fn()
let ehAdmin = true

vi.mock('@/hooks/useLeads', () => ({
  useLeads: (...a: unknown[]) => mockUseLeads(...a),
  useCorrigeEstagio: () => ({ mutate: mockMutate, isPending: false, isError: false }),
}))
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ clinicId: 'c1', ehAdmin }) }))
vi.mock('@/hooks/useClinic', () => ({
  useClinic: () => ({ data: { max_future_dates: 5, batch_message_template: null } }),
}))
vi.mock('@/hooks/useAvailabilityRules', () => ({ useAvailabilityRules: () => ({ data: { data: [] } }) }))
vi.mock('@/pages/pacientes/components/BatchMessageModal', () => ({
  BatchMessageModal: ({ patients }: { patients: { id: string }[] }) => (
    <div data-testid="modal">{patients.length} destinatarios</div>
  ),
}))

const lead = (over: Partial<Lead>): Lead =>
  ({
    id: 'l1',
    clinic_id: 'c1',
    phone: '5511999990000',
    name: 'Maria',
    booked: false,
    source: 'landing-page',
    first_appointment_id: null,
    first_appointment_value: null,
    raw_message: null,
    first_contact_status: null,
    first_contact_at: null,
    conversation_started_at: null,
    conversation_status: null,
    has_whatsapp_chat: null,
    whatsapp_last_message_at: null,
    first_contact_channel: null,
    can_start_bot: null,
    bot_block_reason: null,
    bot_block_message: null,
    can_unmark_contact: null,
    contact_started: null,
    contact_started_source: null,
    contact_started_message: null,
    conversion_status: null,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
    stage: 'SUMIU',
    stage_reason: null,
    stage_source: 'REGRA',
    stage_updated_at: null,
    ultima_mensagem_em: '2026-11-10T00:00:00Z',
    ultima_mensagem_de: 'NOS',
    dias_parado: 14,
    ...over,
  }) as Lead

function monta(leads: Lead[], por_estagio: Record<string, number> = {}) {
  mockUseLeads.mockReturnValue({
    data: {
      status: 'SUCCESS',
      leads,
      total: leads.length,
      totals: { total: leads.length, convertidos: 0, nao_convertidos: leads.length, por_estagio },
      conversions: null,
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })
  return render(<CrmPage />)
}

describe('CrmPage', () => {
  beforeEach(() => {
    mockUseLeads.mockReset()
    mockMutate.mockReset()
    ehAdmin = true
  })

  it('chips mostram a contagem e filtram', () => {
    monta([lead({})], { SUMIU: 7 })
    const chip = screen.getByRole('button', { name: /Sumiu/ })
    expect(chip).toHaveTextContent('7')
    fireEvent.click(chip)
    expect(mockUseLeads).toHaveBeenLastCalledWith(expect.objectContaining({ stage: 'SUMIU', orderBy: 'dias_parado' }))
  })

  it('mostra o motivo e a fonte do estagio', () => {
    monta([lead({ stage: 'NAO_AGENDOU', stage_reason: 'achou caro', stage_source: 'MODELO' })])
    expect(screen.getByText('achou caro')).toBeInTheDocument()
    expect(screen.getByLabelText('Sugerido pelo modelo')).toBeInTheDocument()
  })

  it('clicar no estagio abre o popover e salvar chama a mutation', () => {
    monta([lead({})])
    fireEvent.click(screen.getByRole('button', { name: /Corrigir estágio de Maria/ }))
    fireEvent.change(screen.getByLabelText('Estágio'), { target: { value: 'NAO_AGENDOU' } })
    fireEvent.change(screen.getByPlaceholderText('ex.: achou caro'), { target: { value: 'mora longe' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(mockMutate).toHaveBeenCalledWith(
      { leadId: 'l1', stage: 'NAO_AGENDOU', reason: 'mora longe' },
      expect.anything(),
    )
  })

  it('fato da agenda nao abre popover', () => {
    monta([lead({ stage: 'AGENDOU' })])
    expect(screen.queryByRole('button', { name: /Corrigir estágio/ })).toBeNull()
    // o chip e o badge mostram o mesmo rotulo
    expect(screen.getAllByText('Agendou').length).toBeGreaterThanOrEqual(2)
  })

  it('lead sem estagio diz que aguarda o processamento', () => {
    monta([lead({ stage: null, stage_source: null, dias_parado: null })])
    expect(screen.getByText('Aguardando o processamento')).toBeInTheDocument()
  })

  it('selecionar e disparar abre o modal com os leads', () => {
    monta([lead({}), lead({ id: 'l2', name: 'Joao' })])
    fireEvent.click(screen.getByRole('checkbox', { name: 'Selecionar todos da página' }))
    fireEvent.click(screen.getByRole('button', { name: 'Disparar mensagem' }))
    expect(screen.getByTestId('modal')).toHaveTextContent('2 destinatarios')
  })

  it('STAFF seleciona mas nao dispara', () => {
    ehAdmin = false
    monta([lead({})])
    fireEvent.click(screen.getByRole('checkbox', { name: 'Selecionar Maria' }))
    expect(screen.getByText('1 selecionado')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Disparar mensagem' })).toBeNull()
  })

  it('vazio sem filtro explica a rodada noturna; com filtro orienta a tirar o chip', () => {
    const { unmount } = monta([])
    expect(screen.getByText(/rodada noturna/)).toBeInTheDocument()
    unmount()
    monta([], { SUMIU: 0 })
    fireEvent.click(screen.getByRole('button', { name: /Sumiu/ }))
    expect(screen.getByText(/Tire um chip/)).toBeInTheDocument()
  })

  it('erro mostra o estado de erro com retry', () => {
    mockUseLeads.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error('x'), refetch: vi.fn() })
    render(<CrmPage />)
    expect(screen.getByText('x')).toBeInTheDocument()
  })
})
