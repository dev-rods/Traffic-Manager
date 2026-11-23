import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CreateAppointmentModal } from './CreateAppointmentModal'
import type { Cotacao, PatientWithStats } from '@/types'

const mutateAsync = vi.fn().mockResolvedValue({})
let cotacao: { data?: Cotacao; isPending: boolean; isError: boolean; fetchStatus: string } = {
  data: undefined, isPending: false, isError: false, fetchStatus: 'idle',
}
let pacientes: PatientWithStats[] = []

let ehAdmin = false
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ clinicId: 'c1', isAuthenticated: true, ehAdmin }),
}))
vi.mock('@/hooks/useAppointments', () => ({
  useCreateAppointment: () => ({ mutateAsync, isPending: false }),
  useCotacao: () => cotacao,
}))
// Referência estável: o modal compara `services` com o render anterior para
// escolher o serviço único; um array novo por render viraria loop.
const SERVICOS = [{ id: 's1', name: 'Laser', duration_minutes: 30, price_cents: 20000 }]
vi.mock('@/hooks/useServices', () => ({
  useServices: () => ({ data: SERVICOS }),
}))
vi.mock('@/hooks/useDurationRules', () => ({
  useDurationRules: () => ({ data: { duration_rules: null } }),
}))
vi.mock('@/hooks/usePatients', () => ({
  usePatients: () => ({ data: { items: pacientes } }),
  useCreatePatient: () => ({ mutateAsync: vi.fn() }),
}))
vi.mock('@/hooks/useDebounce', () => ({ useDebounce: <T,>(v: T) => v }))
vi.mock('@/hooks/useAreas', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/useAreas')>()),
  useServiceAreas: () => ({
    data: [
      { service_area_id: 'sa1', service_id: 's1', area_id: 'a1', name: 'Axila', display_order: 1, duration_minutes: null, service_duration_minutes: 30, effective_duration_minutes: 30, price_cents: null, service_price_cents: 20000, effective_price_cents: 20000 },
    ],
  }),
}))
vi.mock('@/hooks/useAvailabilityRules', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/useAvailabilityRules')>()),
  useAvailableSlots: () => ({ data: { slots: ['09:00', '15:00'] }, isLoading: false }),
}))

function paciente(over: Partial<PatientWithStats> = {}): PatientWithStats {
  return {
    id: 'p1',
    name: 'Ana Clara',
    phone: '5511999990001',
    custom_discount_pct: null,
    total_visits: 0,
    ...over,
  } as PatientWithStats
}

function monta() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(
    <QueryClientProvider client={cliente}>
      <CreateAppointmentModal open initialDate="2026-11-27" initialTime="09:00" onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

async function escolhePaciente() {
  await userEvent.type(screen.getByLabelText('Paciente'), 'Ana')
  await userEvent.click(screen.getByRole('button', { name: /Ana Clara/ }))
}

async function marcaAxila() {
  await userEvent.click(screen.getByRole('checkbox', { name: /Axila/ }))
}

const criar = () => screen.getByRole('button', { name: 'Criar agendamento' })
const modo = (nome: string) => screen.getByRole('button', { name: nome })

beforeEach(() => {
  mutateAsync.mockClear()
  mutateAsync.mockResolvedValue({})
  ehAdmin = false
  pacientes = [paciente()]
  cotacao = { data: undefined, isPending: false, isError: false, fetchStatus: 'idle' }
})
afterEach(cleanup)

describe('política da clínica no novo agendamento (PRD 053)', () => {
  it('abre em "Política da clínica" e, ao salvar, não manda desconto: o backend decide', async () => {
    cotacao = {
      data: { originalPriceCents: 20000, discountPct: 10, discountReason: 'first_session', finalPriceCents: 18000, areaCount: 1, isFirst: true },
      isPending: false, isError: false, fetchStatus: 'idle',
    }
    monta()
    expect(modo('Política da clínica')).toHaveAttribute('aria-pressed', 'true')

    await escolhePaciente()
    await marcaAxila()
    // O total vem da cotação, não de uma conta refeita na tela.
    expect(screen.getByText('Desconto (1ª sessão: 10%)')).toBeInTheDocument()
    expect(screen.getByText('R$ 180,00')).toBeInTheDocument()

    await userEvent.click(criar())
    const payload = mutateAsync.mock.calls[0][0]
    expect(payload).not.toHaveProperty('discountPct')
    expect(payload).not.toHaveProperty('discountCents')
    expect(payload).not.toHaveProperty('discountReason')
    expect(payload).not.toHaveProperty('discountPolicy')
  })

  it('"Sem desconto" manda zero com a razão none', async () => {
    monta()
    await escolhePaciente()
    await marcaAxila()
    await userEvent.click(modo('Sem desconto'))
    await userEvent.click(criar())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ discountPct: 0, discountReason: 'none' })
  })

  it('paciente com combinado abre em Personalizado preenchido; trocar para paciente sem combinado volta à política', async () => {
    pacientes = [paciente({ custom_discount_pct: 12.5 }), paciente({ id: 'p2', name: 'Bia Sem Combinado', phone: '5511999990002' })]
    monta()
    await escolhePaciente()
    expect(modo('Personalizado')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Desconto em porcento')).toHaveValue('12,5')

    await userEvent.clear(screen.getByLabelText('Paciente'))
    await userEvent.type(screen.getByLabelText('Paciente'), 'Bia')
    await userEvent.click(screen.getByRole('button', { name: /Bia Sem Combinado/ }))
    expect(modo('Política da clínica')).toHaveAttribute('aria-pressed', 'true')
  })

  it('avisa quando "Primeira vez" discorda do que o banco decidiu', async () => {
    cotacao = {
      data: { originalPriceCents: 20000, discountPct: 0, discountReason: null, finalPriceCents: 20000, areaCount: 1, isFirst: false },
      isPending: false, isError: false, fetchStatus: 'idle',
    }
    monta()
    await escolhePaciente()
    await marcaAxila()
    expect(screen.queryByRole('note')).toBeNull()
    await userEvent.click(screen.getByRole('checkbox', { name: /Primeira vez/ }))
    expect(screen.getByRole('note')).toHaveTextContent('não considera esta a primeira sessão')
  })
})

describe('uma sessão por mês (PRD 056)', () => {
  const conflito = {
    response: {
      status: 409,
      data: {
        code: 'SAME_MONTH_APPOINTMENT',
        existing: { id: 'x1', date: '2026-11-25', time: '14:00', areas: 'Axila', patientName: 'Ana Clara' },
      },
    },
  }

  async function criaComConflito() {
    mutateAsync.mockRejectedValueOnce(conflito)
    monta()
    await escolhePaciente()
    await marcaAxila()
    await userEvent.click(criar())
    return screen.findByRole('group', { name: 'Ana Clara já tem sessão em 25/11/2026 às 14:00.' })
  }

  it('o 409 vira aviso no lugar dos botões; Confirmar reenvia com substituir', async () => {
    const aviso = await criaComConflito()
    expect(aviso).toHaveTextContent('será cancelada e remarcada para 27/11/2026 às 09:00')
    expect(screen.queryByRole('button', { name: 'Criar agendamento' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Manter as duas' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(mutateAsync).toHaveBeenCalledTimes(2)
    expect(mutateAsync.mock.calls[0][0]).not.toHaveProperty('substituir')
    expect(mutateAsync.mock.calls[1][0]).toMatchObject({ ...mutateAsync.mock.calls[0][0], substituir: true })
  })

  it('"Voltar" devolve o formulário sem gravar', async () => {
    await criaComConflito()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(screen.getByRole('button', { name: 'Criar agendamento' })).toBeInTheDocument()
    expect(mutateAsync).toHaveBeenCalledTimes(1)
  })

  it('ADMIN pode manter as duas, com motivo', async () => {
    ehAdmin = true
    await criaComConflito()
    await userEvent.click(screen.getByRole('button', { name: 'Manter as duas' }))
    await userEvent.type(screen.getByLabelText('Motivo para manter as duas sessões'), 'áreas em dias separados')
    await userEvent.click(screen.getByRole('button', { name: 'Manter as duas' }))
    expect(mutateAsync.mock.calls[1][0]).toMatchObject({
      manterAsDuas: true,
      motivoDasDuas: 'áreas em dias separados',
    })
    expect(mutateAsync.mock.calls[1][0]).not.toHaveProperty('substituir')
  })
})

describe('sessão futura em outro mês (PRD 060)', () => {
  const pergunta = {
    response: {
      status: 409,
      data: {
        code: 'OTHER_MONTH_APPOINTMENT',
        existing: { id: 'x2', date: '2026-12-10', time: '09:00', areas: 'Virilha', patientName: 'Ana Clara' },
      },
    },
  }

  async function criaComPergunta() {
    mutateAsync.mockRejectedValueOnce(pergunta)
    monta()
    await escolhePaciente()
    await marcaAxila()
    await userEvent.click(criar())
    return screen.findByRole('group', { name: 'Ana Clara já tem sessão em 10/12/2026 às 09:00.' })
  }

  it('o 409 vira a pergunta; "Remarcar essa sessão" reenvia com remarcarExistente', async () => {
    const aviso = await criaComPergunta()
    expect(aviso).toHaveTextContent('Remarcar essa sessão para 27/11/2026 às 09:00, ou marcar mais uma?')
    expect(screen.queryByRole('button', { name: 'Criar agendamento' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Manter as duas' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remarcar essa sessão' }))
    expect(mutateAsync).toHaveBeenCalledTimes(2)
    expect(mutateAsync.mock.calls[0][0]).not.toHaveProperty('remarcarExistente')
    expect(mutateAsync.mock.calls[1][0]).toMatchObject({ ...mutateAsync.mock.calls[0][0], remarcarExistente: true })
    expect(mutateAsync.mock.calls[1][0]).not.toHaveProperty('substituir')
    expect(mutateAsync.mock.calls[1][0]).not.toHaveProperty('maisUma')
  })

  it('"Marcar mais uma" reenvia com maisUma, sem pedir ADMIN nem motivo', async () => {
    await criaComPergunta()
    await userEvent.click(screen.getByRole('button', { name: 'Marcar mais uma' }))
    expect(mutateAsync).toHaveBeenCalledTimes(2)
    expect(mutateAsync.mock.calls[1][0]).toMatchObject({ maisUma: true })
    expect(mutateAsync.mock.calls[1][0]).not.toHaveProperty('manterAsDuas')
    expect(mutateAsync.mock.calls[1][0]).not.toHaveProperty('remarcarExistente')
  })

  it('"Voltar" devolve o formulário sem gravar', async () => {
    await criaComPergunta()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(screen.getByRole('button', { name: 'Criar agendamento' })).toBeInTheDocument()
    expect(mutateAsync).toHaveBeenCalledTimes(1)
  })
})
