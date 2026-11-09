/**
 * O motivo é obrigatório (PRD 039 §5). O que se protege: não dá para
 * silenciar sem escrever por quê, e o texto não vaza de um contato para o
 * outro.
 */
import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SilenciarModal } from './SilenciarModal'

afterEach(cleanup)

function monta(over: Partial<React.ComponentProps<typeof SilenciarModal>> = {}) {
  const onConfirm = vi.fn()
  const onClose = vi.fn()
  render(
    <SilenciarModal
      open
      phone="5511999990000"
      onClose={onClose}
      onConfirm={onConfirm}
      {...over}
    />,
  )
  return { onConfirm, onClose }
}

describe('SilenciarModal', () => {
  it('nasce com o botão bloqueado: sem motivo, não silencia', () => {
    monta()
    expect(screen.getByRole('button', { name: 'Silenciar bot' })).toBeDisabled()
  })

  it('espaço em branco não conta como motivo', async () => {
    monta()
    await userEvent.type(screen.getByLabelText(/Por que silenciar/), '    ')
    expect(screen.getByRole('button', { name: 'Silenciar bot' })).toBeDisabled()
  })

  it('com motivo escrito, confirma com o texto sem espaços nas pontas', async () => {
    const { onConfirm } = monta()
    await userEvent.type(screen.getByLabelText(/Por que silenciar/), '  atendimento manual  ')
    await userEvent.click(screen.getByRole('button', { name: 'Silenciar bot' }))
    expect(onConfirm).toHaveBeenCalledWith('atendimento manual')
  })

  it('avisa que o lembrete continua saindo (decisão §4.1)', () => {
    monta()
    expect(screen.getByText(/lembrete de sessão continua sendo enviado/i)).toBeInTheDocument()
  })

  it('diz que nenhum prazo traz o bot de volta', () => {
    monta()
    expect(screen.getByText(/nenhum prazo\s+traz ele de volta/i)).toBeInTheDocument()
  })
})
