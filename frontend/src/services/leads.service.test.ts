import { describe, it, expect, vi, beforeEach } from 'vitest'
import { leadsService } from './leads.service'
import { api } from './api'

vi.mock('./api', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

const mockApi = api as unknown as { get: ReturnType<typeof vi.fn> }

const CLINIC_ID = 'clinic-123'

describe('leadsService.list', () => {
  beforeEach(() => vi.clearAllMocks())

  // O filtro por origem vale porque viaja ate o servidor. A tela pede
  // limit=100 e o corte acontece no banco: se `excludeSource` parasse aqui,
  // a pagina voltaria a contar quem chegou direto no WhatsApp sem erro nenhum.
  it('manda excludeSource como query param', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { status: 'SUCCESS', leads: [], total: 0 } })

    await leadsService.list(CLINIC_ID, { excludeSource: 'whatsapp', limit: 100 })

    expect(mockApi.get).toHaveBeenCalledWith(
      `/clinics/${CLINIC_ID}/leads`,
      { params: { excludeSource: 'whatsapp', limit: 100 } }
    )
  })

  it('sem filtro nao inventa parametro', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { status: 'SUCCESS', leads: [], total: 0 } })

    await leadsService.list(CLINIC_ID)

    expect(mockApi.get).toHaveBeenCalledWith(`/clinics/${CLINIC_ID}/leads`, { params: undefined })
  })
})
