import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Confirmacao } from './Confirmacao'

function monta(over: Partial<Parameters<typeof Confirmacao>[0]> = {}) {
  const props = {
    pergunta: 'Mandar o link para (11) 99999-0001 pelo WhatsApp?',
    acao: 'Enviar',
    onConfirmar: vi.fn(),
    onVoltar: vi.fn(),
    ...over,
  }
  render(<Confirmacao {...props} />)
  return props
}

describe('Confirmacao (PRD 053)', () => {
  it('mostra a pergunta, o detalhe e os dois botões', () => {
    monta({ detalhe: 'A cobrança é criada no Asaas.' })
    expect(screen.getByRole('group', { name: /Mandar o link/ })).toBeInTheDocument()
    expect(screen.getByText('A cobrança é criada no Asaas.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeInTheDocument()
  })

  it('a ação nasce com foco: quem já leu confirma com Enter', () => {
    monta()
    expect(screen.getByRole('button', { name: 'Enviar' })).toHaveFocus()
  })

  it('confirmar chama uma vez; Voltar e Escape não executam', async () => {
    const props = monta()
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(props.onConfirmar).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    await userEvent.keyboard('{Escape}')
    expect(props.onVoltar).toHaveBeenCalledTimes(2)
    expect(props.onConfirmar).toHaveBeenCalledTimes(1)
  })

  it('carregando: os dois botões travam', () => {
    monta({ loading: true })
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled()
  })
})
