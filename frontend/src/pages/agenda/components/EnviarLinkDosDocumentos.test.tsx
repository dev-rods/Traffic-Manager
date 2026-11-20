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

/** O primeiro clique abre a confirmação (PRD 053); o segundo envia. */
async function pedeEnvio(rotulo = 'Enviar link dos documentos') {
  await userEvent.click(screen.getByRole('button', { name: rotulo }))
  expect(mutate).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
}

describe('EnviarLinkDosDocumentos (PRD 048)', () => {
  it('nada sai no primeiro clique; Voltar não envia (PRD 053)', async () => {
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm="2026-11-16T10:00:00Z" telefone="5511999990001" />)
    await userEvent.click(screen.getByRole('button', { name: 'Reenviar link dos documentos' }))
    expect(mutate).not.toHaveBeenCalled()
    expect(
      screen.getByRole('group', { name: 'Reenviar o link do termo e da ficha para (11) 99999-0001 pelo WhatsApp?' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Último envio em/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(mutate).not.toHaveBeenCalled()
  })

  it('envia e mostra quando foi', async () => {
    mutate.mockImplementation((_id: string, opts: Opts) =>
      opts.onSuccess({
        link: 'https://documentos.x/c/documentos',
        sent: true,
        consent_link_sent_at: '2026-11-17T14:20:00Z',
      })
    )
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm={null} />)
    await pedeEnvio()
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
    await pedeEnvio()
    expect(screen.getByLabelText('Link dos documentos')).toHaveValue('https://documentos.x/c/documentos')
    expect(screen.getByRole('button', { name: 'Copiar' })).toBeInTheDocument()
  })

  it('regra do servidor vira toast com a mensagem', async () => {
    mutate.mockImplementation((_id: string, opts: Opts) =>
      opts.onError({ response: { data: { message: 'Esta sessão já passou.' } } })
    )
    render(<EnviarLinkDosDocumentos appointmentId="a1" linkEnviadoEm={null} />)
    await pedeEnvio()
    expect(showToast).toHaveBeenCalledWith({ message: 'Esta sessão já passou.', variant: 'error' })
  })
})
