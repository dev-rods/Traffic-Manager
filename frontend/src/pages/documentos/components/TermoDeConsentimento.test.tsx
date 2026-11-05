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

vi.mock('@/hooks/useConsents', () => ({
  useConsentsDoPaciente: () => consulta,
  useAbrirDocumentoDoTermo: () => ({ mutate: abrir, isPending: false, isError: false }),
}))

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
    ...over,
  }
}

beforeEach(() => {
  abrir.mockReset()
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

  it('vazio ensina onde se assina', () => {
    consulta = { ...consulta, data: { consents: [], consent_enabled: true, term_version: '2026-11' } }
    render(<TermoDeConsentimento patientId="p1" />)
    expect(screen.getByText('Nenhum termo assinado')).toBeInTheDocument()
    expect(screen.getByText(/assina o termo no check-in/)).toBeInTheDocument()
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
})
