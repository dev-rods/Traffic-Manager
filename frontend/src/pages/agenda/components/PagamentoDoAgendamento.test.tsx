import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PagamentoDoAgendamento } from './PagamentoDoAgendamento'
import type { Appointment } from '@/types'

const mutate = vi.fn()
const enviarLink = vi.fn()
const showToast = vi.fn()
let mutacao: { data?: { id: string; status: string }; isSuccess: boolean } = { isSuccess: false }

vi.mock('@/hooks/useCaixa', () => ({
  useReceberDinheiro: () => ({ mutate, isPending: false, ...mutacao }),
  useEnviarLink: () => ({ mutate: enviarLink, isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    checked_in_at: null,
    payment_id: null,
    payment_method: null,
    payment_status: null,
    payment_paid_at: null,
    ...over,
  } as Appointment
}

beforeEach(() => {
  mutate.mockReset()
  mutacao = { isSuccess: false }
})

describe('PagamentoDoAgendamento', () => {
  it('não pago e com valor: oferece o link pelo WhatsApp (PRD 029)', async () => {
    render(<PagamentoDoAgendamento appointment={agendamento({ final_price_cents: 13500 })} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link pelo WhatsApp' }))
    expect(enviarLink).toHaveBeenCalledWith(
      { appointmentId: 'a1', cpf: undefined },
      expect.any(Object)
    )
  })

  it('link já enviado: mostra a situação e reenvia o mesmo', () => {
    render(
      <PagamentoDoAgendamento
        appointment={agendamento({
          final_price_cents: 13500,
          payment_id: 'p1',
          payment_method: 'LINK',
          payment_status: 'PENDING',
        })}
      />
    )
    expect(screen.getByText('Link enviado')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reenviar link pelo WhatsApp' })).toBeInTheDocument()
  })

  it('pago: sem link', () => {
    render(
      <PagamentoDoAgendamento
        appointment={agendamento({
          final_price_cents: 13500,
          payment_status: 'PAID',
          payment_method: 'LINK',
        })}
      />
    )
    expect(screen.getByText(/^Pago · Link \(WhatsApp\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /link/i })).not.toBeInTheDocument()
  })

  it('sem check-in nem pagamento', () => {
    render(<PagamentoDoAgendamento appointment={agendamento()} />)
    expect(screen.getByText('Não feito')).toBeInTheDocument()
    expect(screen.getByText('Não pago')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('pago por Pix, com a hora', () => {
    render(
      <PagamentoDoAgendamento
        appointment={agendamento({
          checked_in_at: '2026-10-19T12:50:00Z',
          payment_id: 'p1',
          payment_method: 'PIX',
          payment_status: 'PAID',
          payment_paid_at: '2026-10-19T12:52:00Z',
        })}
      />
    )
    expect(screen.getByText(/^Feito às/)).toBeInTheDocument()
    expect(screen.getByText(/^Pago · Pix às/)).toBeInTheDocument()
  })

  it('dinheiro: a recepção dá a baixa', async () => {
    render(
      <PagamentoDoAgendamento
        appointment={agendamento({
          payment_id: 'p1',
          payment_method: 'CASH',
          payment_status: 'AWAITING_CASH',
        })}
      />
    )
    expect(screen.getByText('Aguardando dinheiro')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Recebi em dinheiro' }))
    expect(mutate).toHaveBeenCalledWith('p1', expect.any(Object))
  })

  it('depois da baixa mostra pago, sem esperar a agenda recarregar', () => {
    mutacao = { isSuccess: true, data: { id: 'p1', status: 'PAID' } }
    render(
      <PagamentoDoAgendamento
        appointment={agendamento({
          payment_id: 'p1',
          payment_method: 'CASH',
          payment_status: 'AWAITING_CASH',
        })}
      />
    )
    expect(screen.getByText(/^Pago · Dinheiro/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Recebi em dinheiro' })).not.toBeInTheDocument()
  })
})
