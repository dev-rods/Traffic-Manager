import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EnviarLinkDePagamento } from './EnviarLinkDePagamento'

type Opcoes = { onSuccess?: (r: unknown) => void; onError?: (e: unknown) => void }
const mutate = vi.fn<(vars: unknown, opcoes: Opcoes) => void>()
const showToast = vi.fn()

vi.mock('@/hooks/useCaixa', () => ({
  useEnviarLink: () => ({ mutate, isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))

const SUCESSO = {
  payment: { id: 'p1', status: 'PENDING' },
  invoiceUrl: 'https://asaas/i/1',
  sent: true,
}

beforeEach(() => {
  mutate.mockReset()
  showToast.mockReset()
})

describe('EnviarLinkDePagamento (PRD 029)', () => {
  it('envia e avisa', async () => {
    mutate.mockImplementation((_, o) => o.onSuccess?.(SUCESSO))
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' }))
    expect(mutate).toHaveBeenCalledWith({ appointmentId: 'a1', cpf: undefined }, expect.any(Object))
    expect(showToast).toHaveBeenCalledWith({ message: 'Link de pagamento enviado pelo WhatsApp' })
  })

  it('sem CPF conhecido: pede o CPF e manda de novo com ele', async () => {
    mutate.mockImplementationOnce((_, o) =>
      o.onError?.({ response: { data: { code: 'CPF_REQUIRED', message: 'Informe o CPF' } } })
    )
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' }))
    const campo = screen.getByLabelText(/CPF de quem vai pagar/)
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
    await userEvent.type(campo, '52998224725')
    expect(campo).toHaveValue('529.982.247-25')
    mutate.mockImplementationOnce((_, o) => o.onSuccess?.(SUCESSO))
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(mutate).toHaveBeenLastCalledWith(
      { appointmentId: 'a1', cpf: '52998224725' },
      expect.any(Object)
    )
    expect(screen.queryByLabelText(/CPF de quem vai pagar/)).not.toBeInTheDocument()
  })

  it('WhatsApp falhou: mostra o link para copiar', async () => {
    mutate.mockImplementation((_, o) => o.onSuccess?.({ ...SUCESSO, sent: false }))
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente />)
    await userEvent.click(screen.getByRole('button', { name: 'Reenviar link pelo WhatsApp' }))
    expect(screen.getByText(/O WhatsApp não enviou/)).toBeInTheDocument()
    expect(screen.getByLabelText('Link de pagamento')).toHaveValue('https://asaas/i/1')
    expect(showToast).not.toHaveBeenCalled()
  })

  it('erro do backend vira toast com a mensagem dele', async () => {
    mutate.mockImplementation((_, o) =>
      o.onError?.({ response: { data: { message: 'Este agendamento já está pago.' } } })
    )
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' }))
    expect(showToast).toHaveBeenCalledWith({
      message: 'Este agendamento já está pago.',
      variant: 'error',
    })
  })
})
