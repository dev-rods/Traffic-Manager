import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EnviarLinkDosDocumentos } from './EnviarLinkDosDocumentos'

const mutate = vi.fn()
const showToast = vi.fn()

vi.mock('@/hooks/useConsents', () => ({
  useEnviarLinkDosDocumentos: () => ({ mutate, isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))

type Resultado = { link: string; sent: boolean; consent_link_sent_at: string | null }
type Opts = { onSuccess: (r: Resultado) => void; onError: (e: unknown) => void }

beforeEach(() => {
  mutate.mockReset()
  showToast.mockReset()
})

describe('EnviarLinkDosDocumentos (PRD 048)', () => {
  it('envia e mostra quando foi', async () => {
    mutate.mockImplementation((_id: string, opts: Opts) =>
      opts.onSuccess({
        link: 'https://documentos.x/c/documentos',
        sent: true,
        consent_link_sent_at: '2026-11-17T14:20:00Z',
      })
    )
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm={null} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link dos documentos' }))
    expect(mutate).toHaveBeenCalledWith('a1', expect.anything())
    expect(showToast).toHaveBeenCalledWith({ message: 'Link dos documentos enviado pelo WhatsApp' })
    expect(screen.getByText(/Link enviado em/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reenviar link dos documentos' })).toBeInTheDocument()
  })

  it('já enviado antes: botão de reenviar e a data', () => {
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm="2026-11-16T10:00:00Z" />)
    expect(screen.getByRole('button', { name: 'Reenviar link dos documentos' })).toBeInTheDocument()
    expect(screen.getByText(/Link enviado em/)).toBeInTheDocument()
  })

  it('WhatsApp falhou: o link fica para copiar', async () => {
    mutate.mockImplementation((_id: string, opts: Opts) =>
      opts.onSuccess({ link: 'https://documentos.x/c/documentos', sent: false, consent_link_sent_at: null })
    )
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm={null} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link dos documentos' }))
    expect(screen.getByLabelText('Link dos documentos')).toHaveValue('https://documentos.x/c/documentos')
    expect(screen.getByRole('button', { name: 'Copiar' })).toBeInTheDocument()
  })

  it('regra do servidor vira toast com a mensagem', async () => {
    mutate.mockImplementation((_id: string, opts: Opts) =>
      opts.onError({ response: { data: { message: 'Esta sessão já passou.' } } })
    )
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm={null} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link dos documentos' }))
    expect(showToast).toHaveBeenCalledWith({ message: 'Esta sessão já passou.', variant: 'error' })
  })
})
