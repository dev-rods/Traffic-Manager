import { describe, it, expect, vi, beforeEach } from 'vitest'
import { leadsService } from './leads.service'
import { api } from './api'

vi.mock('./api', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

const mockApi = api as unknown as { get: ReturnType<typeof vi.fn> }
const mockPost = (api as unknown as { post: ReturnType<typeof vi.fn> }).post

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

describe('acoes de inicio de conversa', () => {
  beforeEach(() => vi.clearAllMocks())

  it('iniciarPeloBot chama o endpoint do lead', async () => {
    mockPost.mockResolvedValueOnce({ data: { status: 'SUCCESS', leadId: 'abc' } })

    await leadsService.iniciarPeloBot('abc')

    expect(mockPost).toHaveBeenCalledWith('/leads/abc/iniciar-pelo-bot')
  })

  // Um endpoint so para marcar e desmarcar: dois endpoints exigiriam o frontend
  // saber o estado atual para escolher qual chamar, e ele erraria justamente
  // quando outra atendente tivesse mexido no meio tempo.
  it('alternarContatoManual usa um endpoint so para marcar e desmarcar', async () => {
    mockPost.mockResolvedValue({ data: { status: 'SUCCESS', first_contact_channel: 'HUMANO' } })

    await leadsService.alternarContatoManual('abc')
    await leadsService.alternarContatoManual('abc')

    expect(mockPost).toHaveBeenNthCalledWith(1, '/leads/abc/marcar-contatado')
    expect(mockPost).toHaveBeenNthCalledWith(2, '/leads/abc/marcar-contatado')
  })
})
