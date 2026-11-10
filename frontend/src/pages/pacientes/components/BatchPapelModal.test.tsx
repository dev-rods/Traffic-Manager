import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BatchPapelModal } from './BatchPapelModal'
import { todayStr } from '@/utils/dateHelpers'
import type { PatientWithStats } from '@/types'

const registerPaper = vi.fn()

vi.mock('@/services/consents.service', () => ({
  consentsService: {
    registerPaper: (...args: unknown[]) => registerPaper(...args),
  },
}))
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ clinicId: 'c1' }) }))
vi.mock('@/hooks/useOverlayLock', () => ({ useOverlayLock: () => undefined }))

function paciente(id: string, name: string): PatientWithStats {
  return {
    id,
    clinic_id: 'c1',
    phone: '5511999990000',
    name,
    gender: 'F',
    cpf: null,
    birth_date: null,
    email: null,
    custom_discount_pct: null,
    skin_type: null,
    created_at: '',
    updated_at: '',
    total_visits: 0,
    last_visit: null,
    next_visit: null,
    total_spent_cents: 0,
    last_message_at: null,
    consent_status: null,
  }
}

const PACIENTES = [paciente('p1', 'Paciente Teste Um'), paciente('p2', 'Paciente Teste Dois'), paciente('p3', 'Paciente Teste Tres')]

function renderiza(onDone = vi.fn(), onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <BatchPapelModal open patients={PACIENTES} onClose={onClose} onDone={onDone} />
    </QueryClientProvider>
  )
  return { onDone, onClose }
}

beforeEach(() => registerPaper.mockReset())
afterEach(cleanup)

/**
 * "Assinado em papel" em lote (PRD 047, §7.2 B): uma data para todos, com o
 * aviso em destaque. Roda na ordem, um por vez, pela rota unitária; quem já
 * tinha termo vigente aparece como "Já tinha" (o servidor responde 200 em vez
 * de 201 e não grava).
 */
describe('BatchPapelModal', () => {
  it('avisa que a data é uma só e começa em hoje', () => {
    renderiza()
    expect(screen.getByText(/A mesma data vale para todas as pessoas selecionadas/)).toBeInTheDocument()
    const data = screen.getByLabelText('Assinado em') as HTMLInputElement
    expect(data.value).toBe(todayStr())
    expect(data.max).toBe(todayStr())
    expect(screen.getByRole('button', { name: 'Registrar 3' })).toBeInTheDocument()
  })

  it('roda na ordem com a data e mostra registrado, já tinha e erro', async () => {
    registerPaper
      .mockResolvedValueOnce({ consent: {}, created: true })
      .mockResolvedValueOnce({ consent: {}, created: false })
      .mockRejectedValueOnce({ response: { data: { message: 'Sem permissão' } } })
    const { onDone } = renderiza()

    const data = screen.getByLabelText('Assinado em')
    await userEvent.clear(data)
    await userEvent.type(data, '2026-10-20')
    await userEvent.click(screen.getByRole('button', { name: 'Registrar 3' }))

    await waitFor(() => expect(screen.getByText('Registro concluído')).toBeInTheDocument())
    expect(registerPaper.mock.calls).toEqual([
      ['c1', 'p1', '2026-10-20'],
      ['c1', 'p2', '2026-10-20'],
      ['c1', 'p3', '2026-10-20'],
    ])
    expect(screen.getByText('Registrado')).toBeInTheDocument()
    expect(screen.getByText('Já tinha')).toBeInTheDocument()
    expect(screen.getByText('Erro')).toHaveAttribute('title', 'Sem permissão')
    expect(screen.getByText('1 registrado')).toBeInTheDocument()
    expect(screen.getByText('1 já tinha termo vigente')).toBeInTheDocument()
    expect(screen.getByText('1 erro')).toBeInTheDocument()

    // O X do Modal também se chama "Fechar"; o do rodapé é o último.
    await userEvent.click(screen.getAllByRole('button', { name: 'Fechar' }).slice(-1)[0])
    expect(onDone).toHaveBeenCalledWith(1)
  })

  it('tirar alguém da seleção antes de rodar', async () => {
    registerPaper.mockResolvedValue({ consent: {}, created: true })
    renderiza()
    await userEvent.click(screen.getByRole('button', { name: 'Remover Paciente Teste Dois da seleção' }))
    expect(screen.getByRole('button', { name: 'Registrar 2' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Registrar 2' }))
    await waitFor(() => expect(screen.getByText('Registro concluído')).toBeInTheDocument())
    expect(registerPaper).toHaveBeenCalledTimes(2)
    expect(registerPaper).not.toHaveBeenCalledWith('c1', 'p2', expect.anything())
  })

  it('cancelar antes de rodar não chama onDone', async () => {
    const { onDone, onClose } = renderiza()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onClose).toHaveBeenCalled()
    expect(onDone).not.toHaveBeenCalled()
    expect(registerPaper).not.toHaveBeenCalled()
  })
})
