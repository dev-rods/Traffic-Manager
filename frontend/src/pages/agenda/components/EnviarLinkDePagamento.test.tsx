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

/** O primeiro clique abre a confirmação (PRD 053); o segundo envia. */
async function pedeEnvio(rotulo = 'Enviar link pelo WhatsApp') {
  await userEvent.click(screen.getByRole('button', { name: rotulo }))
  expect(mutate).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
}

describe('EnviarLinkDePagamento (PRD 029)', () => {
  it('nada sai no primeiro clique: a confirmação diz quanto e para quem (PRD 053)', async () => {
    render(
      <EnviarLinkDePagamento appointmentId="a1" linkPendente={false} valorCents={19500} telefone="5511999990001" />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' }))
    expect(mutate).not.toHaveBeenCalled()
    expect(
      // O formatador usa espaço inviolável em "R$ 195,00"; o nome acessível não normaliza.
      screen.getByRole('group', { name: /^Mandar o link de cobrança de R\$.195,00 para \(11\) 99999-0001 pelo WhatsApp\?$/ }),
    ).toBeInTheDocument()
    expect(screen.getByText('A cobrança é criada no Asaas.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' })).toBeInTheDocument()
  })

  it('reenvio avisa que não cria cobrança nova', async () => {
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente />)
    await userEvent.click(screen.getByRole('button', { name: 'Reenviar link pelo WhatsApp' }))
    expect(screen.getByRole('group', { name: 'Reenviar o link de cobrança para a paciente pelo WhatsApp?' })).toBeInTheDocument()
    expect(screen.getByText(/não cria cobrança nova/)).toBeInTheDocument()
  })

  it('envia e avisa', async () => {
    mutate.mockImplementation((_, o) => o.onSuccess?.(SUCESSO))
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await pedeEnvio()
    expect(mutate).toHaveBeenCalledWith({ appointmentId: 'a1', cpf: undefined }, expect.any(Object))
    expect(showToast).toHaveBeenCalledWith({ message: 'Link de pagamento enviado pelo WhatsApp' })
  })

  it('sem CPF conhecido: pede o CPF e manda de novo com ele', async () => {
    mutate.mockImplementationOnce((_, o) =>
      o.onError?.({ response: { data: { code: 'CPF_REQUIRED', message: 'Informe o CPF' } } })
    )
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await pedeEnvio()
    // O CPF vem DEPOIS da confirmação e não pede outra.
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
    await pedeEnvio('Reenviar link pelo WhatsApp')
    expect(screen.getByText(/O WhatsApp não enviou/)).toBeInTheDocument()
    expect(screen.getByLabelText('Link de pagamento')).toHaveValue('https://asaas/i/1')
    expect(showToast).not.toHaveBeenCalled()
  })

  it('erro do backend vira toast com a mensagem dele', async () => {
    mutate.mockImplementation((_, o) =>
      o.onError?.({ response: { data: { message: 'Este agendamento já está pago.' } } })
    )
    render(<EnviarLinkDePagamento appointmentId="a1" linkPendente={false} />)
    await pedeEnvio()
    expect(showToast).toHaveBeenCalledWith({
      message: 'Este agendamento já está pago.',
      variant: 'error',
    })
  })
})
