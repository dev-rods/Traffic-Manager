import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CustomerInfoForm } from './CustomerInfoForm'

describe('CustomerInfoForm', () => {
  it('mostra erros de validação e não chama onSubmit com dados inválidos', async () => {
    const onSubmit = vi.fn()
    render(<CustomerInfoForm onSubmit={onSubmit} submitting={false} />)

    await userEvent.click(screen.getByRole('button', { name: /finalizar/i }))

    expect(await screen.findByText(/digite seu nome completo/i)).toBeInTheDocument()
    expect(await screen.findByText(/celular inválido/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('formata o celular enquanto o usuário digita e envia os dados válidos', async () => {
    const onSubmit = vi.fn()
    render(<CustomerInfoForm onSubmit={onSubmit} submitting={false} />)

    await userEvent.type(screen.getByLabelText(/nome/i), 'Maria Silva')
    await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')

    expect(screen.getByLabelText(/celular/i)).toHaveValue('(11) 98765-4321')

    await userEvent.click(screen.getByRole('button', { name: /finalizar/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toEqual({ fullName: 'Maria Silva', phone: '(11) 98765-4321' })
  })
})
