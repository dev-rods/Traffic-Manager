import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { BatchMessageModal } from './BatchMessageModal'
import type { PatientWithStats } from '@/types'

/**
 * O modal e a fonte unica das datas: o texto que a paciente le e as datas que
 * o bot oferece precisam ser as mesmas. Antes eram duas listas (19/10/2026).
 */
vi.mock('@/hooks/useMessages', () => ({
  useSendBatchMessages: () => ({
    send: vi.fn(),
    results: [],
    isSending: false,
    isCheckingDelivery: false,
    progress: { sent: 0, total: 0 },
    reset: vi.fn(),
  }),
}))

const DATAS = ['2026-10-21', '2026-10-28', '2026-11-04', '2026-11-11']
const PACIENTE = { id: 'p1', name: 'Ana Clara', phone: '5511999990000' } as PatientWithStats

function renderizar(clinicTemplate?: string | null) {
  return render(
    <BatchMessageModal
      open
      patients={[PACIENTE]}
      availableDates={DATAS}
      clinicTemplate={clinicTemplate}
      onClose={vi.fn()}
      onDone={vi.fn()}
    />
  )
}

describe('BatchMessageModal: texto e datas são a mesma lista', () => {
  it('nasce com as três primeiras datas marcadas e no texto', () => {
    renderizar()
    const texto = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(texto.value).toContain('21/10, 28/10, 04/11')
    expect(texto.value).not.toContain('11/11')
  })

  it('desmarcar uma data tira a data do texto', async () => {
    renderizar()
    await userEvent.click(screen.getByRole('button', { name: '28/10' }))
    const texto = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(texto.value).toContain('21/10, 04/11')
    expect(texto.value).not.toContain('28/10')
  })

  it('o texto da clínica entra com as datas no {datas}', () => {
    renderizar('Oi {nome}! Temos {datas}. Vem?')
    const texto = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(texto.value).toBe('Oi {nome}! Temos 21/10, 28/10, 04/11. Vem?')
  })

  it('depois de editar à mão, mudar as datas não sobrescreve o texto', async () => {
    renderizar()
    const texto = screen.getByRole('textbox') as HTMLTextAreaElement
    await userEvent.clear(texto)
    await userEvent.type(texto, 'Texto meu')
    await userEvent.click(screen.getByRole('button', { name: '11/11' }))
    expect(texto.value).toBe('Texto meu')

    // E dá para voltar ao padrão, já com a seleção nova.
    await userEvent.click(screen.getByRole('button', { name: 'Voltar ao texto padrão' }))
    expect(texto.value).toContain('11/11')
  })
})
