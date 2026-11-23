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

describe('ConflitoDoMes - sessão futura em outro mês (PRD 060)', () => {
  const EXISTING_DEZ = { ...EXISTING, date: '2026-12-10', time: '09:00', areas: 'Virilha' }

  it('pergunta "remarcar ou mais uma?" em vez de avisar que será substituída', () => {
    const props = monta({ existing: EXISTING_DEZ, variante: 'outro_mes', onMaisUma: vi.fn() })
    const grupo = screen.getByRole('group', { name: 'Ana Clara já tem sessão em 10/12/2026 às 09:00.' })
    expect(grupo).toHaveTextContent('Remarcar essa sessão para 28/11/2026 às 10:00, ou marcar mais uma?')
    expect(grupo).not.toHaveTextContent('será cancelada')
    expect(grupo).toHaveTextContent('Áreas: Virilha')
    expect(screen.getByRole('button', { name: 'Remarcar essa sessão' })).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Confirmar' })).not.toBeInTheDocument()
    void props
  })

  it('os três botões: Voltar, Marcar mais uma, Remarcar essa sessão', async () => {
    const props = monta({ existing: EXISTING_DEZ, variante: 'outro_mes', onMaisUma: vi.fn() })
    await userEvent.click(screen.getByRole('button', { name: 'Marcar mais uma' }))
    expect(props.onMaisUma).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Remarcar essa sessão' }))
    expect(props.onConfirmar).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(props.onVoltar).toHaveBeenCalledTimes(1)
    expect(props.onManterAsDuas).not.toHaveBeenCalled()
  })

  it('"Manter as duas" não existe em outro mês, nem para ADMIN: não quebra a regra do mês', () => {
    monta({ existing: EXISTING_DEZ, variante: 'outro_mes', ehAdmin: true, onMaisUma: vi.fn() })
    expect(screen.queryByRole('button', { name: 'Manter as duas' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Marcar mais uma' })).toBeEnabled()
  })

  it('sem variante continua sendo o aviso do mesmo mês', () => {
    monta()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Marcar mais uma' })).not.toBeInTheDocument()
  })
})
