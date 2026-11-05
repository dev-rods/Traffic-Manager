import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TermoDoAgendamento } from './TermoDoAgendamento'
import type { Appointment } from '@/types'

const dispensar = vi.fn()
const registrarPapel = vi.fn()
const showToast = vi.fn()

vi.mock('@/hooks/useConsents', () => ({
  useDispensarTermo: () => ({ mutate: dispensar, isPending: false, isSuccess: false }),
  useRegistrarPapel: () => ({ mutate: registrarPapel, isPending: false, isSuccess: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))
vi.mock('@/hooks/useOverlayLock', () => ({ useOverlayLock: () => undefined }))

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    patient_id: 'p1',
    status: 'CONFIRMED',
    consent_enabled: true,
    consent_status: null,
    consent_waived_at: null,
    consent_waived_reason: null,
    consent_waived_by: null,
    ...over,
  } as Appointment
}

beforeEach(() => {
  dispensar.mockReset()
  registrarPapel.mockReset()
})

describe('TermoDoAgendamento', () => {
  it('sem versão configurada não aparece', () => {
    const { container } = render(<TermoDoAgendamento appointment={agendamento({ consent_enabled: false })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('assinado: situação sem botões', () => {
    render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'SIGNED' })} />)
    expect(screen.getByText('Assinado')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('em papel e dispensado também não oferecem ação', () => {
    const { rerender } = render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'PAPER' })} />)
    expect(screen.getByText('Em papel')).toBeInTheDocument()
    rerender(
      <TermoDoAgendamento
        appointment={agendamento({
          consent_waived_at: '2026-11-04T12:00:00Z',
          consent_waived_by: 'Joana',
          consent_waived_reason: 'RECUSOU',
        })}
      />
    )
    expect(screen.getByText('Dispensado por Joana em 04/11/26 (recusou assinar no ipad)')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('pendente: dispensar pede o motivo e chama o serviço', async () => {
    render(<TermoDoAgendamento appointment={agendamento()} />)
    expect(screen.getByText('Pendente')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Dispensar nesta sessão' }))
    await userEvent.selectOptions(screen.getByLabelText('Motivo'), 'OUTRO')
    expect(screen.getByRole('button', { name: 'Dispensar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Descreva o motivo'), 'veio sem óculos')
    await userEvent.click(screen.getByRole('button', { name: 'Dispensar' }))
    expect(dispensar).toHaveBeenCalledWith(
      { appointmentId: 'a1', reason: 'OUTRO', note: 'veio sem óculos' },
      expect.any(Object)
    )
  })

  it('pendente: assinado em papel manda a data', async () => {
    render(<TermoDoAgendamento appointment={agendamento()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Assinado em papel' }))
    const data = screen.getByLabelText('Assinado em')
    await userEvent.clear(data)
    await userEvent.type(data, '2026-11-01')
    await userEvent.click(screen.getByRole('button', { name: 'Registrar' }))
    expect(registrarPapel).toHaveBeenCalledWith(
      { patientId: 'p1', signedAt: '2026-11-01' },
      expect.any(Object)
    )
  })

  it('assinando no iPad: ainda pendente para a recepção', () => {
    render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'SIGNING' })} />)
    expect(screen.getByText('Assinando no iPad')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dispensar nesta sessão' })).toBeInTheDocument()
  })

  it('sessão cancelada pendente: sem ação', () => {
    render(<TermoDoAgendamento appointment={agendamento({ status: 'NO_SHOW' })} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
