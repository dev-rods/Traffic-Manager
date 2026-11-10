import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RegistrarPapelModal } from './RegistrarPapelModal'
import { todayStr } from '@/utils/dateHelpers'

const registrarPapel = vi.fn()
const showToast = vi.fn()

vi.mock('@/hooks/useConsents', () => ({
  useRegistrarPapel: () => ({ mutate: registrarPapel, isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast }) }))
vi.mock('@/hooks/useOverlayLock', () => ({ useOverlayLock: () => undefined }))

type Opcoes = { onSuccess?: () => void; onError?: (e: unknown) => void }

beforeEach(() => {
  registrarPapel.mockReset()
  showToast.mockReset()
})

/**
 * O modal "Termo assinado em papel" numa peça só (PRD 047): a agenda, a pasta
 * do paciente e a linha da lista usam este. A data começa em hoje, não passa
 * de hoje, e o toast de erro mostra a mensagem do servidor (o 403 de quem não
 * tem `agenda.escrever` chega por aqui).
 */
describe('RegistrarPapelModal', () => {
  it('começa em hoje e não deixa data futura', () => {
    render(<RegistrarPapelModal open patientId="p1" onClose={vi.fn()} />)
    const data = screen.getByLabelText('Assinado em') as HTMLInputElement
    expect(data.value).toBe(todayStr())
    expect(data.max).toBe(todayStr())
  })

  it('registra com a data, avisa, fecha e chama onRegistrado', async () => {
    const onClose = vi.fn()
    const onRegistrado = vi.fn()
    registrarPapel.mockImplementation((_v: unknown, o: Opcoes) => o.onSuccess?.())
    render(<RegistrarPapelModal open patientId="p1" onClose={onClose} onRegistrado={onRegistrado} />)

    const data = screen.getByLabelText('Assinado em')
    await userEvent.clear(data)
    await userEvent.type(data, '2026-11-01')
    await userEvent.click(screen.getByRole('button', { name: 'Registrar' }))

    expect(registrarPapel).toHaveBeenCalledWith({ patientId: 'p1', signedAt: '2026-11-01' }, expect.any(Object))
    expect(showToast).toHaveBeenCalledWith({ message: 'Termo em papel registrado' })
    expect(onClose).toHaveBeenCalled()
    expect(onRegistrado).toHaveBeenCalled()
  })

  it('erro: mostra a mensagem do servidor e não fecha', async () => {
    const onClose = vi.fn()
    registrarPapel.mockImplementation((_v: unknown, o: Opcoes) =>
      o.onError?.({ response: { data: { message: 'Sem permissão para escrever na agenda' } } })
    )
    render(<RegistrarPapelModal open patientId="p1" onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Registrar' }))

    expect(showToast).toHaveBeenCalledWith({
      message: 'Sem permissão para escrever na agenda',
      variant: 'error',
    })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('cancelar fecha sem registrar', async () => {
    const onClose = vi.fn()
    render(<RegistrarPapelModal open patientId="p1" onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onClose).toHaveBeenCalled()
    expect(registrarPapel).not.toHaveBeenCalled()
  })
})
