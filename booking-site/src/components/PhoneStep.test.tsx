import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PhoneStep } from './PhoneStep'

describe('PhoneStep (PRD 061)', () => {
  it('segue só com o celular completo, formatado', async () => {
    const onContinue = vi.fn()
    render(<PhoneStep onContinue={onContinue} aguardando={false} />)

    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/celular/i), '119876543')
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/celular/i), '21')
    expect(screen.getByLabelText(/celular/i)).toHaveValue('(11) 98765-4321')

    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(onContinue).toHaveBeenCalledWith('(11) 98765-4321')
  })

  it('número de fora do Brasil: escolhe o país, sem precisar do + (PRD 067)', async () => {
    const onContinue = vi.fn()
    render(<PhoneStep onContinue={onContinue} aguardando={false} />)
    expect(screen.queryByText(/Comece com \+/)).toBeNull()
    expect(screen.getByLabelText('País')).toHaveValue('55')
    await userEvent.selectOptions(screen.getByLabelText('País'), '1')
    await userEvent.type(screen.getByLabelText(/celular/i), '(202) 555-0147')
    expect(screen.getByLabelText(/celular/i)).toHaveValue('2025550147')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(onContinue).toHaveBeenCalledWith('+12025550147')
  })

  it('"Outro país" pede o código; sem ele não segue', async () => {
    const onContinue = vi.fn()
    render(<PhoneStep onContinue={onContinue} aguardando={false} />)
    await userEvent.selectOptions(screen.getByLabelText('País'), 'outro')
    await userEvent.type(screen.getByLabelText(/celular/i), '12345678')
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Código do país'), '45')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(onContinue).toHaveBeenCalledWith('+4512345678')
  })

  it('voltar à etapa reabre o número estrangeiro no país certo', () => {
    render(<PhoneStep defaultValue="+12025550147" onContinue={vi.fn()} aguardando={false} />)
    expect(screen.getByLabelText('País')).toHaveValue('1')
    expect(screen.getByLabelText(/celular/i)).toHaveValue('2025550147')
  })

  it('enquanto a sessão desta aba é conferida, não deixa seguir', async () => {
    const onContinue = vi.fn()
    render(<PhoneStep defaultValue="(11) 98765-4321" onContinue={onContinue} aguardando />)
    expect(screen.getByRole('button', { name: /continuar/i })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: /continuar/i }))
    expect(onContinue).not.toHaveBeenCalled()
  })

  it('avisa que o código vem por WhatsApp e que o desconto personalizado aparece depois dele', () => {
    render(<PhoneStep onContinue={vi.fn()} aguardando={false} />)
    expect(screen.getByText(/código por WhatsApp/)).toBeInTheDocument()
    expect(screen.getByText('desconto personalizado')).toBeInTheDocument()
  })
})
