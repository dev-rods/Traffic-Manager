import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MyAppointmentsModal } from './MyAppointmentsModal'
import { bookingService } from '@/services/booking.service'
import type { Appointment } from '@/types'

vi.mock('@/services/booking.service')

const APPOINTMENT = {
  id: 'ap1',
  service_name: 'Depilação a Laser',
  full_name: 'Maria Silva',
  appointment_date: '2026-10-25',
  start_time: '10:00:00',
  final_price_cents: 29700,
} as Appointment

function renderModal() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MyAppointmentsModal open clinicId="c1" onClose={() => {}} />
    </QueryClientProvider>
  )
}

describe('MyAppointmentsModal', () => {
  beforeEach(() => {
    vi.mocked(bookingService.sendOtp).mockResolvedValue({ status: 'SUCCESS' })
    vi.mocked(bookingService.confirmOtp).mockResolvedValue('tok')
    vi.mocked(bookingService.myAppointments).mockResolvedValue([APPOINTMENT])
  })

  async function verify() {
    renderModal()
    await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    await userEvent.type(await screen.findByLabelText('Código de verificação'), '123456')
    await userEvent.click(screen.getByRole('button', { name: /confirmar|verificar/i }))
  }

  // Mandar `(11) 98765-4321` deixava a lista vazia para quem tinha acabado de
  // agendar (o backend comparava com `5511987654321`).
  it('lista pelo telefone no formato da API', async () => {
    await verify()
    expect(await screen.findByText('Depilação a Laser')).toBeInTheDocument()
    expect(bookingService.myAppointments).toHaveBeenCalledWith('c1', '5511987654321', 'tok')
  })

  it('mostra o nome de quem agendou, porque o telefone pode ser de mais de uma pessoa', async () => {
    await verify()
    expect(await screen.findByText('Maria Silva')).toBeInTheDocument()
  })

  it('cancela pelo telefone no formato da API', async () => {
    vi.mocked(bookingService.cancelAppointment).mockResolvedValue({
      ...APPOINTMENT,
      status: 'CANCELLED',
    })
    await verify()
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar agendamento' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))
    expect(bookingService.cancelAppointment).toHaveBeenCalledWith(
      'c1',
      'ap1',
      '5511987654321',
      'tok'
    )
  })
})
