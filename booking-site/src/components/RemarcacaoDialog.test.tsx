import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RemarcacaoDialog } from './RemarcacaoDialog'

const EXISTING = { id: 'x1', date: '2026-11-25', time: '14:00', areas: 'Axilas' }

function monta(over: Partial<Parameters<typeof RemarcacaoDialog>[0]> = {}) {
  const props = {
    existing: EXISTING,
    date: '2026-11-28',
    time: '10:00',
    clinicPhone: '5511999990000',
    confirming: false,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    ...over,
  }
  render(<RemarcacaoDialog {...props} />)
  return props
}

describe('RemarcacaoDialog (PRD 056)', () => {
  it('diz qual sessão será substituída por qual, no tom curto', () => {
    monta()
    const dialog = screen.getByRole('dialog', { name: 'Você já tem uma sessão este mês' })
    expect(dialog).toHaveTextContent('Sua sessão de 25/11/2026 às 14:00 será substituída por 28/11/2026 às 10:00. Confirmar?')
    expect(dialog).toHaveTextContent('Qualquer dúvida, fale com a clínica.')
    expect(dialog).not.toHaveTextContent(/manter/i)
  })

  it('o botão do WhatsApp abre a conversa com a clínica', () => {
    monta()
    expect(screen.getByRole('link', { name: 'Falar no WhatsApp' })).toHaveAttribute(
      'href',
      'https://wa.me/5511999990000'
    )
  })

  it('sem telefone cadastrado, o botão some e o texto fica', () => {
    monta({ clinicPhone: null })
    expect(screen.queryByRole('link', { name: 'Falar no WhatsApp' })).not.toBeInTheDocument()
    expect(screen.getByText('Qualquer dúvida, fale com a clínica.')).toBeInTheDocument()
  })

  it('"Confirmar remarcação" e "Voltar" chamam o que devem', async () => {
    const props = monta()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar remarcação' }))
    expect(props.onConfirm).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(props.onCancel).toHaveBeenCalledTimes(1)
  })

  it('fechado quando não há sessão existente', () => {
    monta({ existing: null })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
