import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FiltrosDePacientes } from './FiltrosDePacientes'
import { contaFiltrosAtivos } from './contagemDeFiltros'

afterEach(cleanup)

function renderiza(extra: Partial<React.ComponentProps<typeof FiltrosDePacientes>> = {}) {
  const onConsent = vi.fn()
  render(
    <FiltrosDePacientes
      nextVisit="all"
      lastMessage="all"
      lastVisitBefore=""
      onNextVisit={vi.fn()}
      onLastMessage={vi.fn()}
      onLastVisitBefore={vi.fn()}
      {...extra}
    />
  )
  return { onConsent }
}

/** O filtro "Termo e anamnese" (PRD 047) só existe para clínica com termo configurado. */
describe('FiltrosDePacientes - termo', () => {
  it('sem onConsent o campo não aparece', () => {
    renderiza()
    expect(screen.queryByLabelText('Termo e anamnese')).toBeNull()
  })

  it('com onConsent oferece sem/com termo vigente e avisa a escolha', async () => {
    const onConsent = vi.fn()
    renderiza({ consent: 'all', onConsent })
    const campo = screen.getByLabelText('Termo e anamnese')
    await userEvent.selectOptions(campo, 'missing')
    expect(onConsent).toHaveBeenCalledWith('missing')
    await userEvent.selectOptions(campo, 'ok')
    expect(onConsent).toHaveBeenCalledWith('ok')
  })

  it('no drawer ganha rótulo', () => {
    renderiza({ consent: 'all', onConsent: vi.fn(), empilhado: true })
    expect(screen.getAllByText('Termo e anamnese').length).toBeGreaterThan(0)
  })
})

describe('contaFiltrosAtivos', () => {
  it('conta o filtro do termo quando ligado', () => {
    const base = { nextVisit: 'all' as const, lastMessage: 'all' as const, lastVisitBefore: '' }
    expect(contaFiltrosAtivos(base)).toBe(0)
    expect(contaFiltrosAtivos({ ...base, consent: 'all' })).toBe(0)
    expect(contaFiltrosAtivos({ ...base, consent: 'missing' })).toBe(1)
    expect(contaFiltrosAtivos({ ...base, nextVisit: 'with', consent: 'ok' })).toBe(2)
  })
})
