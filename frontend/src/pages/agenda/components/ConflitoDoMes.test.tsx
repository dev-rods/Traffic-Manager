import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConflitoDoMes } from './ConflitoDoMes'

const EXISTING = { id: 'x1', date: '2026-11-25', time: '14:00', areas: 'Axilas', patientName: 'Ana Clara' }

function monta(over: Partial<Parameters<typeof ConflitoDoMes>[0]> = {}) {
  const props = {
    existing: EXISTING,
    novaData: '2026-11-28',
    novaHora: '10:00',
    modo: 'criar' as const,
    ehAdmin: false,
    onConfirmar: vi.fn(),
    onManterAsDuas: vi.fn(),
    onVoltar: vi.fn(),
    ...over,
  }
  render(<ConflitoDoMes {...props} />)
  return props
}

describe('ConflitoDoMes (PRD 056)', () => {
  it('diz quem, quando, e o que acontece ao confirmar', () => {
    monta()
    const grupo = screen.getByRole('group', { name: 'Ana Clara já tem sessão em 25/11/2026 às 14:00.' })
    expect(grupo).toHaveTextContent('Ao confirmar, essa sessão será cancelada e remarcada para 28/11/2026 às 10:00.')
    expect(grupo).toHaveTextContent('Áreas: Axilas')
  })

  it('ao mover, o texto diz que ESTA sessão é remarcada', () => {
    monta({ modo: 'mover' })
    expect(screen.getByRole('group')).toHaveTextContent('essa sessão será cancelada e esta será remarcada para')
  })

  it('STAFF só vê Confirmar e Voltar', async () => {
    const props = monta()
    expect(screen.queryByRole('button', { name: 'Manter as duas' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(props.onConfirmar).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(props.onVoltar).toHaveBeenCalledTimes(1)
  })

  it('ADMIN tem "Manter as duas", que exige motivo', async () => {
    const props = monta({ ehAdmin: true })
    await userEvent.click(screen.getByRole('button', { name: 'Manter as duas' }))
    const confirmar = screen.getByRole('button', { name: 'Manter as duas' })
    expect(confirmar).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Motivo para manter as duas sessões'), '  áreas em dias separados ')
    await userEvent.click(confirmar)
    expect(props.onManterAsDuas).toHaveBeenCalledWith('áreas em dias separados')
    expect(props.onConfirmar).not.toHaveBeenCalled()
  })

  it('Escape volta', async () => {
    const props = monta()
    await userEvent.keyboard('{Escape}')
    expect(props.onVoltar).toHaveBeenCalledTimes(1)
  })
})
