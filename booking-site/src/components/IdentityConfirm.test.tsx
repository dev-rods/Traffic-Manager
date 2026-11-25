import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IdentityConfirm } from './IdentityConfirm'

describe('IdentityConfirm (PRD 061)', () => {
  it('cadastro completo: "Sou eu" confirma sem pedir nada', async () => {
    const onConfirm = vi.fn()
    render(<IdentityConfirm nome="Edna" faltam={[]} onConfirm={onConfirm} onNotMe={vi.fn()} submitting={false} />)

    expect(screen.getByText(/Olá,/)).toHaveTextContent('Olá, Edna! É você?')
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Sou eu' }))
    expect(onConfirm).toHaveBeenCalledWith({})
  })

  it('cadastro incompleto: "Sou eu" abre só os campos que faltam, sem o nome', async () => {
    const onConfirm = vi.fn()
    render(
      <IdentityConfirm nome="Edna" faltam={['cpf', 'email']} onConfirm={onConfirm} onNotMe={vi.fn()} submitting={false} />
    )
    await userEvent.click(screen.getByRole('button', { name: 'Sou eu' }))
    expect(onConfirm).not.toHaveBeenCalled()

    expect(screen.getByLabelText(/cpf/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/nascimento/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^nome/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/celular/i)).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'edna@x.com')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    await waitFor(() => expect(onConfirm).toHaveBeenCalled())
    expect(onConfirm.mock.calls[0][0]).toMatchObject({ cpf: '529.982.247-25', email: 'edna@x.com' })
  })

  it('"Não sou eu" devolve o controle', async () => {
    const onNotMe = vi.fn()
    render(<IdentityConfirm nome="Edna" faltam={[]} onConfirm={vi.fn()} onNotMe={onNotMe} submitting={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'Não sou eu' }))
    expect(onNotMe).toHaveBeenCalled()
  })

  it('mostra o erro do servidor', () => {
    render(
      <IdentityConfirm nome="Edna" faltam={[]} onConfirm={vi.fn()} onNotMe={vi.fn()} submitting={false} error="Deu ruim" />
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Deu ruim')
  })
})
