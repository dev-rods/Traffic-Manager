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
      isFirstVisit: false,
    }
    mockApi.post.mockResolvedValueOnce({ data: { id: 'new-appt', ...payload } })
    await appointmentsService.create(payload)
    expect(mockApi.post).toHaveBeenCalledWith('/appointments', payload)
  })
})

describe('lembrete da agenda do dia (PRD 027)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('a previa manda simular=true como query param', async () => {
    mockApi.post.mockResolvedValueOnce({ data: { status: 'SUCCESS', enfileirados: 3 } })
    await appointmentsService.lembrarAgendaDoDia(CLINIC_ID, '2026-11-06', true)
    expect(mockApi.post).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/agenda/2026-11-06/lembretes`,
      null,
      { params: { simular: 'true' } },
    )
  })

  it('o envio real nao manda params', async () => {
    mockApi.post.mockResolvedValueOnce({ data: { status: 'SUCCESS', enfileirados: 3 } })
    await appointmentsService.lembrarAgendaDoDia(CLINIC_ID, '2026-11-06', false)
    expect(mockApi.post).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/agenda/2026-11-06/lembretes`,
      null,
      { params: undefined },
    )
  })

  // `confirmado` vai SOZINHO no corpo: o backend recusa combinado com outros
  // campos, porque confirmacao e coluna e nao status.
  it('confirmar presenca e um PUT so com confirmado', async () => {
    mockApi.put.mockResolvedValueOnce({ data: { status: 'SUCCESS' } })
    await appointmentsService.confirmarPresenca('appt-1', true)
    expect(mockApi.put).toHaveBeenCalledWith('/appointments/appt-1', { confirmado: true })
  })
})
