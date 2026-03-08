import { describe, it, expect, vi, beforeEach } from 'vitest'
import { appointmentsService } from './appointments.service'
import { api } from './api'

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
}

const CLINIC_ID = 'clinic-123'

describe('appointmentsService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list calls correct endpoint', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { appointments: [], total: 0 } })
    await appointmentsService.list(CLINIC_ID, { date: '2026-03-08' })
    expect(mockApi.get).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/appointments`,
      { params: { date: '2026-03-08' } }
    )
  })

  it('cancel sends PUT with status=CANCELLED', async () => {
    mockApi.put.mockResolvedValueOnce({ data: { id: 'appt-1', status: 'CANCELLED' } })
    await appointmentsService.cancel('appt-1')
    expect(mockApi.put).toHaveBeenCalledWith(
      '/appointments/appt-1',
      { status: 'CANCELLED' }
    )
  })

  it('create sends payload to /appointments', async () => {
    const payload = {
      clinicId: CLINIC_ID,
      phone: '5511999990000',
      serviceId: 's-1',
      date: '2026-03-08',
      time: '09:00',
    }
    mockApi.post.mockResolvedValueOnce({ data: { id: 'new-appt', ...payload } })
    await appointmentsService.create(payload)
    expect(mockApi.post).toHaveBeenCalledWith('/appointments', payload)
  })
})
