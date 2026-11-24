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
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ fullName: 'Maria Silva', phone: '(11) 98765-4321' })
  })

  it('avisa quando o celular fica válido (para refazer a cotação) e quando deixa de ser', async () => {
    const onPhoneChange = vi.fn()
    render(<CustomerInfoForm onSubmit={vi.fn()} submitting={false} onPhoneChange={onPhoneChange} />)

    await userEvent.type(screen.getByLabelText(/celular/i), '1198765432')
    expect(onPhoneChange).toHaveBeenLastCalledWith('(11) 98765-432')

    await userEvent.type(screen.getByLabelText(/celular/i), '1')
    expect(onPhoneChange).toHaveBeenLastCalledWith('(11) 98765-4321')

    await userEvent.type(
      screen.getByLabelText(/celular/i),
      '{backspace}{backspace}{backspace}{backspace}{backspace}{backspace}'
    )
    expect(onPhoneChange).toHaveBeenLastCalledWith(null)
  })

  it('usa o rótulo de envio recebido', () => {
    render(
      <CustomerInfoForm onSubmit={vi.fn()} submitting={false} submitLabel="Confirmar agendamento" />
    )
    expect(screen.getByRole('button', { name: 'Confirmar agendamento' })).toBeInTheDocument()
  })

  it('semCelular e semNome (PRD 061): só os campos do cadastro, sem exigir nome nem celular', async () => {
    const onSubmit = vi.fn()
    render(
      <CustomerInfoForm
        semCelular
        semNome
        camposFaltantes={['cpf']}
        onSubmit={onSubmit}
        submitting={false}
        submitLabel="Continuar"
      />
    )
    expect(screen.queryByLabelText(/celular/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^nome/i)).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ cpf: '529.982.247-25' })
  })

  it('semCelular com nome (cadastro de quem é novo): o nome continua obrigatório', async () => {
    const onSubmit = vi.fn()
    render(<CustomerInfoForm semCelular camposFaltantes={['email']} onSubmit={onSubmit} submitting={false} />)
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'a@b.com')
    await userEvent.click(screen.getByRole('button', { name: /finalizar/i }))
    expect(await screen.findByText(/digite seu nome completo/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
