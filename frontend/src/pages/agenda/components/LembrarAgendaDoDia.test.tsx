import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { LembrarAgendaDoDia } from './LembrarAgendaDoDia'
import type { LembretesDoDiaResponse } from '@/types'

const mutate = vi.fn()
vi.mock('@/hooks/useAppointments', () => ({
  useLembrarAgendaDoDia: () => ({ mutate, isPending: false, isError: false }),
}))

const previa: LembretesDoDiaResponse = {
  status: 'SUCCESS', enfileirados: 8, ja_lembrados: 3, sem_telefone: 1, enfileirados_antes: 0,
  send_at: '2026-11-05T15:00:00Z', adiados_para: null, tem_link_de_autoatendimento: true,
}

type Opts = { onSuccess: (r: LembretesDoDiaResponse) => void }

describe('LembrarAgendaDoDia', () => {
  // Entre chaves de proposito: `mockReset()` devolve o mock, e o vitest trata
  // uma funcao devolvida por beforeEach como cleanup - chamaria `mutate()`
  // sem argumentos ao fim de cada teste.
  beforeEach(() => {
    mutate.mockReset()
  })

  it('mostra a previa e envia com o numero certo', () => {
    mutate.mockImplementation((_vars: { simular: boolean }, opts: Opts) => opts.onSuccess(previa))
    render(<LembrarAgendaDoDia dia="2026-11-06" />)
    fireEvent.click(screen.getByRole('button', { name: 'Lembrar agenda do dia' }))
    expect(screen.getByText(/3 já lembrados/)).toBeInTheDocument()
    expect(screen.getByText(/1 sem telefone/)).toBeInTheDocument()
    expect(screen.getByText(/envia o link do site/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Enviar para 8' }))
    expect(mutate).toHaveBeenLastCalledWith({ dia: '2026-11-06', simular: false }, expect.anything())
    expect(screen.getByRole('status')).toHaveTextContent('8 lembretes a caminho')
  })

  it('sem site avisa que o bot resolve pela conversa', () => {
    mutate.mockImplementation((_v: unknown, opts: Opts) => opts.onSuccess({ ...previa, tem_link_de_autoatendimento: false }))
    render(<LembrarAgendaDoDia dia="2026-11-06" />)
    fireEvent.click(screen.getByRole('button', { name: 'Lembrar agenda do dia' }))
    expect(screen.getByText(/não tem site/)).toBeInTheDocument()
  })

  it('avisa quando o lote foi adiado e nao deixa enviar sem ninguem', () => {
    mutate.mockImplementation((_v: unknown, opts: Opts) =>
      opts.onSuccess({ ...previa, enfileirados: 0, adiados_para: '2026-11-06T07:59:00Z' }))
    render(<LembrarAgendaDoDia dia="2026-11-06" />)
    fireEvent.click(screen.getByRole('button', { name: 'Lembrar agenda do dia' }))
    expect(screen.getByText(/Fora do horário/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar para 0' })).toBeDisabled()
  })

  it('desabilitado nao abre a previa', () => {
    render(<LembrarAgendaDoDia dia="2026-11-04" disabled />)
    expect(screen.getByRole('button', { name: 'Lembrar agenda do dia' })).toBeDisabled()
    expect(mutate).not.toHaveBeenCalled()
  })
})
