import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConsentSignStep } from './ConsentSignStep'
import type { Consent } from '@/types'

// O widget da ClickSign "assina" na hora: chama o callback de signed ao montar.
vi.mock('@/lib/clicksignWidget', () => ({
  loadClicksign: () => Promise.resolve(),
  mountClicksign: (
    _signer: string,
    _endpoint: string,
    _container: string,
    onSigned: () => void
  ) => {
    onSigned()
    return () => undefined
  },
}))

// O backend ainda não fechou: continua SIGNING, então a faixa "Assinatura
// recebida" fica na tela.
vi.mock('@/hooks/useCheckin', () => ({
  useConsentStatus: () => ({ data: undefined, refetch: () => Promise.resolve() }),
  useSimulateConsent: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}))

const CONSENT: Consent = {
  id: 'cons-1',
  status: 'SIGNING',
  signerId: 'signer-1',
  widgetEndpoint: 'https://app.clicksign.com',
  test: false,
  canSimulate: false,
  signedAt: null,
}

const SESSION = { phone: '5511999990000', token: 'tok' }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ConsentSignStep: faixa depois da assinatura', () => {
  it('no iPad avisa que vem conferir o agendamento e pagar', async () => {
    render(
      <ConsentSignStep
        clinicId="c1"
        session={SESSION}
        consent={CONSENT}
        onSigned={vi.fn()}
        onRestart={vi.fn()}
      />
    )
    const faixa = (await screen.findByText(/Assinatura recebida!/)).closest('span')!
    expect(faixa).toHaveTextContent('conferir o agendamento e pagar')
  })

  it('pelo celular (PRD 048) não fala em pagamento', async () => {
    render(
      <ConsentSignStep
        clinicId="c1"
        session={SESSION}
        consent={CONSENT}
        onSigned={vi.fn()}
        onRestart={vi.fn()}
        remoto
      />
    )
    const faixa = (await screen.findByText(/Assinatura recebida!/)).closest('span')!
    expect(faixa).toHaveTextContent('estamos registrando o documento.')
    expect(faixa).not.toHaveTextContent(/pagar|agendamento/)
  })
})
