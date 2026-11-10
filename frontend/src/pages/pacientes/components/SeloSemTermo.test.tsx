import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { SeloSemTermo } from './SeloSemTermo'
import { semTermo } from '@/utils/termo'

afterEach(cleanup)

/**
 * "Sem termo" (PRD 047, §7.3 A): só o negativo. `SIGNING` conta como falta,
 * como o DOCS da agenda; sem versão configurada nada é pendente.
 */
describe('SeloSemTermo', () => {
  it('aparece para null e SIGNING; some para SIGNED e PAPER', () => {
    for (const [status, aparece] of [
      [null, true],
      ['SIGNING', true],
      ['SIGNED', false],
      ['PAPER', false],
    ] as const) {
      render(<SeloSemTermo consentEnabled status={status} />)
      expect(screen.queryByText('Sem termo') !== null).toBe(aparece)
      cleanup()
    }
  })

  it('sem versão configurada nunca aparece', () => {
    render(<SeloSemTermo consentEnabled={false} status={null} />)
    expect(screen.queryByText('Sem termo')).toBeNull()
    expect(semTermo(false, null)).toBe(false)
  })

  it('explica no title', () => {
    render(<SeloSemTermo consentEnabled status={null} />)
    expect(screen.getByTitle('Termo e anamnese sem assinatura vigente')).toBeInTheDocument()
  })
})
