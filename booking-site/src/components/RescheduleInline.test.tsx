import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RescheduleInline } from './RescheduleInline'
import { bookingService } from '@/services/booking.service'
import { ApiError } from '@/services/api'
import type { Appointment, BootstrapResponse } from '@/types'

vi.mock('@/services/booking.service')

const APPOINTMENT = {
  id: 'ap1',
  service_id: 's1',
  service_ids: ['s1', 's2'],
  service_area_pairs: [{ serviceId: 's1', areaId: 'a1' }],
  appointment_date: '2026-10-25',
  start_time: '10:00:00',
  status: 'CONFIRMED',
} as Appointment

function renderInline() {
  const onDone = vi.fn()
  const onBack = vi.fn()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <RescheduleInline
        clinicId="c1"
        appointment={APPOINTMENT}
        phone="5511987654321"
        token="tok"
        onDone={onDone}
        onBack={onBack}
      />
    </QueryClientProvider>
  )
  return { onDone, onBack }
}

describe('RescheduleInline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(bookingService.bootstrap).mockResolvedValue({
      clinic: { phone: '11999990000' },
    } as BootstrapResponse)
    vi.mocked(bookingService.availability).mockResolvedValue({
      days: {
        '2026-10-28': { status: 'AVAILABLE', slots: ['09:00', '10:30'] },
      },
    })
  })

  it('pede a grade com o carrinho do agendamento e sem o próprio horário', async () => {
    renderInline()
    expect(await screen.findByRole('button', { name: 'QUA 28 de outubro' })).toBeInTheDocument()
    expect(bookingService.availability).toHaveBeenCalledWith(
      'c1',
      { serviceIds: ['s1', 's2'], serviceAreaPairs: [{ serviceId: 's1', areaId: 'a1' }] },
      'ap1'
    )
  })

  it('escolher o dia mostra os horários e confirmar remarca com date e time', async () => {
    vi.mocked(bookingService.rescheduleAppointment).mockResolvedValue({
      ...APPOINTMENT,
      appointment_date: '2026-10-28',
    })
    const { onDone } = renderInline()

    const confirmar = screen.getByRole('button', { name: 'Confirmar remarcação' })
    expect(confirmar).toBeDisabled()

    await userEvent.click(await screen.findByRole('button', { name: 'QUA 28 de outubro' }))
    await userEvent.click(screen.getByRole('button', { name: '10:30' }))
    await userEvent.click(confirmar)

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(bookingService.rescheduleAppointment).toHaveBeenCalledWith('c1', 'ap1', {
      phone: '5511987654321',
      token: 'tok',
      date: '2026-10-28',
      time: '10:30',
    })
  })

  it('horário que acabou de ser ocupado mostra a mensagem e recarrega a grade', async () => {
    vi.mocked(bookingService.rescheduleAppointment).mockRejectedValue(
      new ApiError('Esse horário acabou de ser ocupado. Escolha outro.', 409)
    )
    const { onDone } = renderInline()

    await userEvent.click(await screen.findByRole('button', { name: 'QUA 28 de outubro' }))
    await userEvent.click(screen.getByRole('button', { name: '09:00' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar remarcação' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Esse horário acabou de ser ocupado. Escolha outro.'
    )
    await waitFor(() => expect(bookingService.availability).toHaveBeenCalledTimes(2))
    expect(onDone).not.toHaveBeenCalled()
  })

  it('voltar não remarca', async () => {
    const { onBack } = renderInline()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(onBack).toHaveBeenCalled()
    expect(bookingService.rescheduleAppointment).not.toHaveBeenCalled()
  })
})
