/**
 * Os campos do cadastro aparecem só para quem ainda não os tem (PRD 032), e
 * cada um valida o formato na hora.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CustomerInfoForm } from './CustomerInfoForm'
import type { CampoDoCadastro } from '@/types'

function monta(faltam: CampoDoCadastro[], onSubmit = vi.fn()) {
  render(<CustomerInfoForm onSubmit={onSubmit} submitting={false} camposFaltantes={faltam} />)
  return onSubmit
}

async function preencheNomeECelular() {
  await userEvent.type(screen.getByLabelText(/nome/i), 'Maria Silva')
  await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')
}

describe('quais campos aparecem', () => {
  it('nada quando o cadastro está completo', () => {
    monta([])
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/nascimento/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/e-mail/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/primeira vez aqui/i)).not.toBeInTheDocument()
  })

  it('só o que falta', () => {
    monta(['email'])
    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()
    expect(screen.getByText(/primeira vez aqui/i)).toBeInTheDocument()
  })
})

describe('validação e envio', () => {
  it('formata o CPF e a data enquanto digita', async () => {
    monta(['cpf', 'birth_date', 'email'])
    await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
    await userEvent.type(screen.getByLabelText(/nascimento/i), '31101990')
    expect(screen.getByLabelText(/cpf/i)).toHaveValue('529.982.247-25')
    expect(screen.getByLabelText(/nascimento/i)).toHaveValue('31/10/1990')
  })

  it('não envia com CPF inválido, data futura ou e-mail sem arroba', async () => {
    const onSubmit = monta(['cpf', 'birth_date', 'email'])
    await preencheNomeECelular()
    await userEvent.type(screen.getByLabelText(/cpf/i), '11111111111')
    await userEvent.type(screen.getByLabelText(/nascimento/i), '01012099')
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'maria')
    await userEvent.click(screen.getByRole('button', { name: /finalizar/i }))

    expect(await screen.findByText('CPF inválido')).toBeInTheDocument()
    expect(screen.getByText('Data inválida')).toBeInTheDocument()
    expect(screen.getByText('E-mail inválido')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('envia os três quando válidos', async () => {
    const onSubmit = monta(['cpf', 'birth_date', 'email'])
    await preencheNomeECelular()
    await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
    await userEvent.type(screen.getByLabelText(/nascimento/i), '31101990')
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'maria@x.com')
    await userEvent.click(screen.getByRole('button', { name: /finalizar/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      fullName: 'Maria Silva',
      cpf: '529.982.247-25',
      birthDate: '31/10/1990',
      email: 'maria@x.com',
    })
  })

  it('enquanto a cotação com o celular não volta, o botão espera', () => {
    render(<CustomerInfoForm onSubmit={vi.fn()} submitting={false} aguardandoCadastro />)
    expect(screen.getByRole('button', { name: 'Verificando cadastro...' })).toBeDisabled()
  })
})
