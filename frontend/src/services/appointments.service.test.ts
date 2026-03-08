import { describe, it, expect, vi, beforeEach } from 'vitest'
import { appointmentsService } from './appointments.service'
import { api } from './api'

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
}

const CLINIC_ID = 'clinic-123'

describe('appointmentsService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list calls correct endpoint', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    await appointmentsService.list(CLINIC_ID, { date: '2026-03-08' })
    expect(mockApi.get).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/appointments`,
      { params: { date: '2026-03-08' } }
    )
  })

  it('cancel sends status=cancelled', async () => {
    mockApi.patch.mockResolvedValueOnce({ data: { id: 'appt-1', status: 'cancelled' } })
    await appointmentsService.cancel(CLINIC_ID, 'appt-1')
    expect(mockApi.patch).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/appointments/appt-1`,
      { status: 'cancelled' }
    )
  })

  it('create sends payload to correct endpoint', async () => {
    const payload = {
      patient_id: 'p-1',
      service_id: 's-1',
      area_ids: ['a-1'],
      professional: 'Dra. Ana',
      scheduled_at: '2026-03-08T12:00:00Z',
    }
    mockApi.post.mockResolvedValueOnce({ data: { id: 'new-appt', ...payload } })
    await appointmentsService.create(CLINIC_ID, payload)
    expect(mockApi.post).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/appointments`,
      payload
    )
  })
})
