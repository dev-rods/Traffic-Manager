import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CancelAppointmentModal } from './CancelAppointmentModal'
import type { Appointment } from '@/types'

vi.mock('@/hooks/useAppointments', () => ({
  useCancelAppointment: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    start_time: '09:00:00',
    end_time: '09:50:00',
    patient_name: 'Ana',
    payment_status: null,
    ...over,
  } as Appointment
}

describe('CancelAppointmentModal', () => {
  it('avisa que cancelar não devolve o dinheiro quando já está pago (PRD 028, M7)', () => {
    render(<CancelAppointmentModal appointment={agendamento({ payment_status: 'PAID' })} onClose={vi.fn()} onReschedule={vi.fn()} />)
    expect(screen.getByText(/Este agendamento já foi pago/)).toBeInTheDocument()
    expect(screen.getByText(/Estornos pendentes/)).toBeInTheDocument()
  })

  it('sem pagamento, sem aviso', () => {
    render(<CancelAppointmentModal appointment={agendamento()} onClose={vi.fn()} onReschedule={vi.fn()} />)
    expect(screen.queryByText(/já foi pago/)).not.toBeInTheDocument()
  })

  // Um terço dos cancelamentos eram remarcações feitas como cancelar + criar
  // (PRD 035). O atalho entrega o agendamento para edição, sem cancelar.
  it('oferece remarcar em vez de cancelar e entrega o agendamento', async () => {
    const onReschedule = vi.fn()
    const a = agendamento()
    render(<CancelAppointmentModal appointment={a} onClose={vi.fn()} onReschedule={onReschedule} />)

    expect(screen.getByText(/A pessoa vai remarcar\?/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remarcar em vez de cancelar' }))

    expect(onReschedule).toHaveBeenCalledWith(a)
  })
})
