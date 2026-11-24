import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PhoneStep } from './PhoneStep'

describe('PhoneStep (PRD 061)', () => {
  it('avisa a cotação quando o celular fica válido e segue só com ele completo', async () => {
    const onPhoneChange = vi.fn()
    const onContinue = vi.fn()
    render(<PhoneStep onPhoneChange={onPhoneChange} onContinue={onContinue} aguardando={false} />)

    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/celular/i), '119876543')
    expect(onPhoneChange).toHaveBeenLastCalledWith(null)

    await userEvent.type(screen.getByLabelText(/celular/i), '21')
    expect(onPhoneChange).toHaveBeenLastCalledWith('(11) 98765-4321')
    expect(screen.getByLabelText(/celular/i)).toHaveValue('(11) 98765-4321')

    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(onContinue).toHaveBeenCalledWith('(11) 98765-4321')
  })

  it('enquanto a cotação com o celular não volta, não deixa seguir', async () => {
    const onContinue = vi.fn()
    render(<PhoneStep defaultValue="(11) 98765-4321" onPhoneChange={vi.fn()} onContinue={onContinue} aguardando />)
    expect(screen.getByRole('button', { name: /continuar/i })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: /continuar/i }))
    expect(onContinue).not.toHaveBeenCalled()
  })

  it('diz que o desconto da paciente aparece aqui', () => {
    render(<PhoneStep onPhoneChange={vi.fn()} onContinue={vi.fn()} aguardando={false} />)
    expect(screen.getByText(/Já é paciente\?/)).toBeInTheDocument()
  })
})
