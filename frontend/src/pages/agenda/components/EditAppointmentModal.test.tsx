/**
 * Alteração com efeito fora da tela não executa no clique (PRD 043).
 *
 * O coração do pedido do André é "não correr o risco de cancelar sem
 * perceber": o que se protege aqui é que NADA é gravado antes de a pessoa ver
 * o que vai mudar. O teste central é o `mutateAsync` não ter sido chamado.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { EditAppointmentModal } from './EditAppointmentModal'
import type { Appointment } from '@/types'

const mutateAsync = vi.fn().mockResolvedValue({})

// Os hooks reais que sobram nos mocks parciais leem a clínica do contexto.
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ clinicId: 'c1', isAuthenticated: true }),
}))

vi.mock('@/hooks/useAppointments', () => ({
  useUpdateAppointment: () => ({ mutateAsync, isPending: false }),
}))
vi.mock('@/hooks/useServices', () => ({
  useServices: () => ({ data: [{ id: 's1', name: 'Laser', duration_minutes: 30, price_cents: 20000 }] }),
}))
vi.mock('@/hooks/useDurationRules', () => ({
  useDurationRules: () => ({ data: { duration_rules: null } }),
}))
// Mock parcial: outros hooks destes módulos são importados por componentes
// filhos, e um mock total os apagaria.
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

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'ap1',
    clinic_id: 'c1',
    patient_name: 'Ana Clara',
    full_name: 'Ana Clara',
    appointment_date: '2026-11-12',
    start_time: '09:00:00',
    service_id: 's1',
    service_name: 'Laser',
    areas: 'Axila',
    area_ids: 'a1',
    notes: '',
    is_first_visit: false,
    manual_duration_minutes: null,
    discount_pct: 0,
    discount_reason: null,
    confirmado_em: null,
    confirmado_por: null,
    payment_status: null,
    status: 'CONFIRMED',
    ...over,
  } as Appointment
}

function monta(over: Partial<Appointment> = {}) {
  // `DateSelect` usa um hook real (mock parcial) e precisa do provider.
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  render(
    <QueryClientProvider client={cliente}>
      <EditAppointmentModal appointment={agendamento(over)} onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

const salvar = () => screen.getByRole('button', { name: 'Salvar alterações' })
const campoHora = () => screen.getByLabelText('Horário manual')

/** O campo é um `input type="time"`, não um select de horários livres. */
async function mudaHorario(para: string) {
  await userEvent.clear(campoHora())
  await userEvent.type(campoHora(), para)
}

beforeEach(() => mutateAsync.mockClear())
afterEach(cleanup)

describe('mudança com efeito fora da tela', () => {
  it('pede confirmação e NÃO grava nada no primeiro clique', async () => {
    monta()

    await mudaHorario('15:00')
    await userEvent.click(salvar())

    expect(mutateAsync).not.toHaveBeenCalled()
    // Título do passo (o botão tem o mesmo texto, por isso o papel).
    expect(screen.getByRole('heading', { name: 'Confirmar alteração' })).toBeInTheDocument()
    expect(screen.getByText('09:00')).toBeInTheDocument()
    expect(screen.getByText('15:00')).toBeInTheDocument()
  })

  it('o resumo nomeia a paciente, para pegar a tela errada', async () => {
    monta()

    await mudaHorario('15:00')
    await userEvent.click(salvar())

    expect(screen.getByText('Ana Clara')).toBeInTheDocument()
  })

  it('"Voltar" não grava e devolve o formulário com a mudança preservada', async () => {
    monta()

    await mudaHorario('15:00')
    await userEvent.click(salvar())
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

    expect(mutateAsync).not.toHaveBeenCalled()
    expect(salvar()).toBeInTheDocument()
    expect(campoHora()).toHaveValue('15:00')
  })

  it('"Confirmar alteração" grava uma vez', async () => {
    monta()

    await mudaHorario('15:00')
    await userEvent.click(salvar())
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar alteração' }))

    expect(mutateAsync).toHaveBeenCalledTimes(1)
    expect(mutateAsync).toHaveBeenCalledWith({
      appointmentId: 'ap1',
      payload: expect.objectContaining({ time: '15:00' }),
    })
  })

  it('avisa que a presença confirmada volta a pendente', async () => {
    monta({ confirmado_em: '2026-11-10T10:00:00Z', confirmado_por: 'PACIENTE' })

    await mudaHorario('15:00')
    await userEvent.click(salvar())

    expect(screen.getByText(/voltará a Pendente/i)).toBeInTheDocument()
    expect(screen.getByText(/não será avisada/i)).toBeInTheDocument()
  })
})

describe('mudança sem efeito fora da tela', () => {
  it('só a observação grava direto, sem resumo', async () => {
    monta()

    await userEvent.type(screen.getByLabelText(/Observa/i), 'trouxe atestado')
    await userEvent.click(salvar())

    expect(screen.queryByText('Confirmar alteração')).toBeNull()
    expect(mutateAsync).toHaveBeenCalledTimes(1)
  })
})
