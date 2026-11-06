import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TermoDoAgendamento } from './TermoDoAgendamento'
import type { Appointment, ListConsentsResponse, PatientConsent } from '@/types'

const dispensar = vi.fn()
const registrarPapel = vi.fn()
const renovar = vi.fn()
const showToast = vi.fn()
let documentos: { data?: ListConsentsResponse } = {}

vi.mock('@/hooks/useConsents', () => ({
  useConsentsDoPaciente: () => documentos,
  useDispensarTermo: () => ({ mutate: dispensar, isPending: false, isSuccess: false }),
  useRegistrarPapel: () => ({ mutate: registrarPapel, isPending: false, isSuccess: false }),
  useRenovarTermo: () => ({ mutate: renovar, isPending: false, isSuccess: false }),
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

function documento(over: Partial<PatientConsent> = {}): PatientConsent {
  return {
    id: 't1',
    appointment_id: 'a1',
    term_version: '2026-12',
    status: 'SIGNED',
    signer_kind: 'PATIENT',
    signer_name: 'Ana Souza',
    image_authorized: true,
    signed_at: '2026-11-05T13:00:00Z',
    paper_signed_at: null,
    paper_registered_by: null,
    has_pdf: true,
    has_zip: false,
    test: false,
    created_at: '2026-11-05T12:55:00Z',
    answers: { gestante: true },
    alertas: [{ key: 'gestante', label: 'Gestante' }],
    has_anamnesis: true,
    revoked_at: null,
    revoked_by: null,
    ...over,
  }
}

beforeEach(() => {
  dispensar.mockReset()
  registrarPapel.mockReset()
  renovar.mockReset()
  documentos = {}
})

describe('TermoDoAgendamento', () => {
  it('sem versão configurada não aparece', () => {
    const { container } = render(<TermoDoAgendamento appointment={agendamento({ consent_enabled: false })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('assinado: situação sem dispensa nem papel', () => {
    render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'SIGNED' })} />)
    expect(screen.getByText('Assinado')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dispensar nesta sessão' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Assinado em papel' })).toBeNull()
  })

  it('assinado com ficha: alertas em vermelho e "Pedir nova assinatura" com confirmação inline (PRD 038)', async () => {
    documentos = { data: { consents: [documento()], consent_enabled: true, term_version: '2026-12' } }
    render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'SIGNED' })} />)
    expect(screen.getByRole('list', { name: 'Alertas da anamnese' })).toHaveTextContent('Gestante')
    await userEvent.click(screen.getByRole('button', { name: 'Pedir nova assinatura' }))
    expect(renovar).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Sim, pedir' }))
    expect(renovar).toHaveBeenCalledWith('t1', expect.any(Object))
  })

  it('documento de versão antiga não é vigente: sem alertas nem renovação', () => {
    documentos = {
      data: { consents: [documento({ term_version: '2026-11' })], consent_enabled: true, term_version: '2026-12' },
    }
    render(<TermoDoAgendamento appointment={agendamento({ consent_status: 'SIGNED' })} />)
    expect(screen.queryByRole('list', { name: 'Alertas da anamnese' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Pedir nova assinatura' })).toBeNull()
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
