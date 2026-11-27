import { describe, it, expect, vi, beforeEach, onTestFinished } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CancelAppointmentModal } from './CancelAppointmentModal'
import type { Appointment } from '@/types'

const mutateAsync = vi.fn().mockResolvedValue({})
vi.mock('@/hooks/useAppointments', () => ({
  useCancelAppointment: () => ({ mutateAsync, isPending: false }),
}))

beforeEach(() => mutateAsync.mockClear())

/** Daqui a N dias, como YYYY-MM-DD local. */
function daqui(dias: number): string {
  const d = new Date()
  d.setDate(d.getDate() + dias)
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
}

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    appointment_date: daqui(5),
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

describe('desfecho pela antecedência (PRD 054)', () => {
  it('com 24 h ou mais é cancelamento, e o botão diz isso', async () => {
    render(<CancelAppointmentModal appointment={agendamento({ appointment_date: daqui(5) })} onClose={vi.fn()} onReschedule={vi.fn()} />)
    expect(screen.getByText(/Vai contar como cancelamento/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Cancelamento/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))
    expect(mutateAsync).toHaveBeenCalledWith({ appointmentId: 'a1' })
  })

  it('sessão passada é falta: o botão vira "Registrar falta" e manda sem sobreposição', async () => {
    render(<CancelAppointmentModal appointment={agendamento({ appointment_date: daqui(-1) })} onClose={vi.fn()} onReschedule={vi.fn()} />)
    expect(screen.getByText(/Vai contar como falta/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Registrar falta' }))
    expect(mutateAsync).toHaveBeenCalledWith({ appointmentId: 'a1' })
  })

  it('trocar o desfecho exige motivo e manda outcome + outcomeReason (decisão 2)', async () => {
    render(<CancelAppointmentModal appointment={agendamento({ appointment_date: daqui(-1) })} onClose={vi.fn()} onReschedule={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /^Cancelamento/ }))
    const confirmar = screen.getByRole('button', { name: 'Confirmar cancelamento' })
    expect(confirmar).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Motivo/), 'avisou doença')
    expect(confirmar).toBeEnabled()
    await userEvent.click(confirmar)
    expect(mutateAsync).toHaveBeenCalledWith({ appointmentId: 'a1', outcome: 'CANCELLED', outcomeReason: 'avisou doença' })
  })

  it('a abertura da agenda do dia é a referência, não a hora da sessão', () => {
    // Sessão amanhã às 23h, agenda abre às 08h: ao meio-dia de hoje faltam 20 h
    // para a abertura (e 35 h para a sessão). O relógio é fixado ao meio-dia:
    // rodando de madrugada a abertura ficava a mais de 24 h e o teste falhava.
    const meioDia = new Date()
    meioDia.setHours(12, 0, 0, 0)
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(meioDia)
    onTestFinished(() => {
      vi.useRealTimers()
    })
    const regras = [{ id: 'r', clinic_id: 'c', day_of_week: new Date(`${daqui(1)}T12:00:00`).getDay(), rule_date: null, start_time: '08:00:00', end_time: '20:00:00', professional_id: null, active: true }]
    render(
      <CancelAppointmentModal
        appointment={agendamento({ appointment_date: daqui(1), start_time: '23:00:00', end_time: '23:30:00' })}
        onClose={vi.fn()}
        onReschedule={vi.fn()}
        regras={regras}
      />,
    )
    expect(screen.getByText(/Vai contar como falta/)).toBeInTheDocument()
  })
})
