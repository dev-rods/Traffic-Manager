import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TermoDeConsentimento } from './TermoDeConsentimento'
import type { ListConsentsResponse, PatientConsent } from '@/types'

const abrir = vi.fn()
let consulta: {
  data?: ListConsentsResponse
  isLoading: boolean
  isError: boolean
  refetch: () => void
} = { isLoading: false, isError: false, refetch: vi.fn() }

const renovar = vi.fn()
const registrarPapel = vi.fn()
vi.mock('@/hooks/useConsents', () => ({
  useConsentsDoPaciente: () => consulta,
  useAbrirDocumentoDoTermo: () => ({ mutate: abrir, isPending: false, isError: false }),
  useRenovarTermo: () => ({ mutate: renovar, isPending: false, isSuccess: false }),
  useRegistrarPapel: () => ({ mutate: registrarPapel, isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('@/hooks/useOverlayLock', () => ({ useOverlayLock: () => undefined }))

function termo(over: Partial<PatientConsent> = {}): PatientConsent {
  return {
    id: 't1',
    appointment_id: 'a1',
    term_version: '2026-11',
    status: 'SIGNED',
    signer_kind: 'PATIENT',
    signer_name: 'Ana Souza',
    image_authorized: true,
    signed_at: '2026-11-04T13:00:00Z',
    paper_signed_at: null,
    paper_registered_by: null,
    has_pdf: true,
    has_zip: false,
    test: false,
    created_at: '2026-11-04T12:55:00Z',
    answers: null,
    alertas: [],
    has_anamnesis: false,
    revoked_at: null,
    revoked_by: null,
    ...over,
  }
}

beforeEach(() => {
  abrir.mockReset()
  registrarPapel.mockReset()
  consulta = { isLoading: false, isError: false, refetch: vi.fn() }
})

describe('TermoDeConsentimento', () => {
  it('carregando', () => {
    consulta = { ...consulta, isLoading: true }
    render(<TermoDeConsentimento patientId="p1" />)
    expect(document.querySelector('[aria-busy="true"]')).toBeInTheDocument()
  })

  it('erro com retry', async () => {
    consulta = { ...consulta, isError: true }
    render(<TermoDeConsentimento patientId="p1" />)
    await userEvent.click(screen.getByRole('button', { name: /tentar/i }))
    expect(consulta.refetch).toHaveBeenCalled()
  })

  it('vazio ensina onde se assina e oferece o papel (PRD 047)', async () => {
    consulta = { ...consulta, data: { consents: [], consent_enabled: true, term_version: '2026-11' } }
    render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.getByText('Nenhum documento assinado')).toBeInTheDocument()
    expect(screen.getByText(/ficha no check-in do iPad/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Assinado em papel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Registrar' }))
    expect(registrarPapel).toHaveBeenCalledWith(
      { patientId: 'p1', signedAt: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) },
      expect.any(Object)
    )
  })

  it('vazio sem versão configurada: sem botão de papel', () => {
    consulta = { ...consulta, data: { consents: [], consent_enabled: false, term_version: null } }
    render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.queryByRole('button', { name: 'Assinado em papel' })).toBeNull()
  })

  it('com documentos mas sem vigente: oferece o papel; com vigente, não (PRD 047)', () => {
    consulta = {
      ...consulta,
      data: {
        consents: [termo({ term_version: '2026-01' })],
        consent_enabled: true,
        term_version: '2026-11',
      },
    }
    const { rerender } = render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.getByRole('button', { name: 'Assinado em papel' })).toBeInTheDocument()

    consulta = {
      ...consulta,
      data: { consents: [termo()], consent_enabled: true, term_version: '2026-11' },
    }
    rerender(<TermoDeConsentimento patientId="p1" />)
    expect(screen.queryByRole('button', { name: 'Assinado em papel' })).toBeNull()
  })

  it('lista as versões e abre o PDF por URL assinada', async () => {
    consulta = {
      ...consulta,
      data: {
        consents: [
          termo(),
          termo({
            id: 't2',
            term_version: '2026-01',
            status: 'PAPER',
            signer_name: null,
            paper_signed_at: '2026-01-10',
            paper_registered_by: 'Joana',
            has_pdf: false,
          }),
          termo({ id: 't3', status: 'SIGNED', signer_kind: 'GUARDIAN', signer_name: 'Carla', test: true, has_zip: true }),
        ],
        consent_enabled: true,
        term_version: '2026-11',
      },
    }
    render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.getAllByText('VIGENTE')).toHaveLength(2)
    expect(screen.getByText('EM PAPEL')).toBeInTheDocument()
    expect(screen.getByText('Joana')).toBeInTheDocument()
    expect(screen.getByText('10/01/2026')).toBeInTheDocument()
    expect(screen.getByText('responsável legal')).toBeInTheDocument()
    expect(screen.getByText('TESTE')).toBeInTheDocument()

    const pdfs = screen.getAllByRole('button', { name: 'Abrir PDF' })
    expect(pdfs[1]).toBeDisabled()
    await userEvent.click(pdfs[0])
    expect(abrir).toHaveBeenCalledWith({ consentId: 't1', kind: 'pdf' })

    const zips = screen.getAllByRole('button', { name: 'Baixar zip' })
    expect(zips[0]).toBeDisabled()
    await userEvent.click(zips[2])
    expect(abrir).toHaveBeenCalledWith({ consentId: 't3', kind: 'zip' })
  })

  it('documento com ficha: mostra as respostas por seção, os alertas e pede nova assinatura (PRD 038)', async () => {
    consulta = {
      ...consulta,
      data: {
        consents: [
          termo({
            term_version: '2026-12',
            has_anamnesis: true,
            answers: { queixa_principal: 'Virilha', gestante: true, hormonal: true, hormonal_quais: 'SOP', fototipo: 'III', fuma: false },
            alertas: [{ key: 'gestante', label: 'Gestante' }],
          }),
          termo({ id: 't0', term_version: '2026-11', status: 'REVOKED', revoked_at: '2026-11-05T10:00:00Z', revoked_by: 'Joana' }),
        ],
        consent_enabled: true,
        term_version: '2026-12',
      },
    }
    window.confirm = vi.fn(() => true)
    render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.getByText('NOVA ASSINATURA PEDIDA')).toBeInTheDocument()
    expect(screen.getByText(/nova assinatura pedida em 05\/11\/2026 por Joana/)).toBeInTheDocument()
    expect(screen.queryByTestId('respostas-da-anamnese')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: 'Ver respostas' }))
    const respostas = screen.getByTestId('respostas-da-anamnese')
    expect(respostas).toHaveTextContent('Gestante')
    expect(respostas).toHaveTextContent('Virilha')
    expect(respostas).toHaveTextContent('SOP')
    expect(respostas).toHaveTextContent('III - Pele clara média')
    expect(respostas).toHaveTextContent('Autodeclarado pela paciente')
    // Condicional cujo pai é "Não" não aparece.
    expect(respostas).not.toHaveTextContent('Data da última dose')

    await userEvent.click(screen.getByRole('button', { name: 'Pedir nova assinatura' }))
    expect(renovar).toHaveBeenCalledWith('t1')
  })
})
