import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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
    render(<CancelAppointmentModal appointment={agendamento({ payment_status: 'PAID' })} onClose={vi.fn()} />)
    expect(screen.getByText(/Este agendamento já foi pago/)).toBeInTheDocument()
    expect(screen.getByText(/Estornos pendentes/)).toBeInTheDocument()
  })

  it('sem pagamento, sem aviso', () => {
    render(<CancelAppointmentModal appointment={agendamento()} onClose={vi.fn()} />)
    expect(screen.queryByText(/já foi pago/)).not.toBeInTheDocument()
  })
})
