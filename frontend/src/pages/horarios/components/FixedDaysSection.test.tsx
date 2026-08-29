import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FixedDaysSection } from './FixedDaysSection'
import type { AvailabilityRule } from '@/types'

function makeRule(id: string, date: string, start: string): AvailabilityRule {
  return {
    id,
    clinic_id: 'clinica-teste',
    day_of_week: null,
    rule_date: date,
    start_time: start,
    end_time: '18:00:00',
    professional_id: null,
    active: true,
  }
}

// Duas datas, sendo que a primeira tem duas faixas.
const RULES = [
  makeRule('r1', '2026-09-15', '09:00:00'),
  makeRule('r2', '2026-09-15', '14:00:00'),
  makeRule('r3', '2026-09-16', '09:00:00'),
]

function renderSection(overrides: Partial<React.ComponentProps<typeof FixedDaysSection>> = {}) {
  const props = {
    rules: RULES,
    maxHeight: 320,
    onAdd: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onDeleteMany: vi.fn().mockResolvedValue(undefined),
    deletingIds: new Set<string>(),
    ...overrides,
  }
  render(<FixedDaysSection {...props} />)
  return props
}

describe('FixedDaysSection', () => {
  it('agrupa faixas por data e ordena cronologicamente', () => {
    renderSection()
    const dates = screen.getAllByText(/\d{2}\/\d{2}\/\d{4}/).map((el) => el.textContent)
    expect(dates).toEqual(['15/09/2026', '16/09/2026'])
  })

  it('ignora regras recorrentes, que pertencem a outra secao', () => {
    const recurring: AvailabilityRule = {
      ...makeRule('r4', '2026-09-17', '09:00:00'),
      rule_date: null,
      day_of_week: 1,
    }
    renderSection({ rules: [...RULES, recurring] })
    expect(screen.getAllByText(/\d{2}\/\d{2}\/\d{4}/)).toHaveLength(2)
  })

  it('exclui todas as faixas das datas selecionadas', async () => {
    const props = renderSection()

    await userEvent.click(screen.getByText('Selecionar'))
    await userEvent.click(screen.getByLabelText('Selecionar 15/09/2026'))

    expect(screen.getByText('1 data selecionada')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))

    await waitFor(() => expect(props.onDeleteMany).toHaveBeenCalled())
    // A data 15/09 tem duas faixas: ambas devem ir, nao so uma.
    const deleted = props.onDeleteMany.mock.calls[0][0] as AvailabilityRule[]
    expect(deleted.map((r) => r.id).sort()).toEqual(['r1', 'r2'])
  })

  it('seleciona todas as datas de uma vez', async () => {
    const props = renderSection()

    await userEvent.click(screen.getByText('Selecionar'))
    await userEvent.click(screen.getByLabelText('Selecionar todas as datas'))

    expect(screen.getByText('2 datas selecionadas')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))
    await waitFor(() => expect(props.onDeleteMany).toHaveBeenCalled())
    expect((props.onDeleteMany.mock.calls[0][0] as AvailabilityRule[])).toHaveLength(3)
  })

  it('sai do modo de selecao apos excluir', async () => {
    renderSection()

    await userEvent.click(screen.getByText('Selecionar'))
    await userEvent.click(screen.getByLabelText('Selecionar 15/09/2026'))
    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /excluir selecionadas/i })).not.toBeInTheDocument(),
    )
  })

  it('nao permite excluir sem nenhuma data selecionada', async () => {
    renderSection()
    await userEvent.click(screen.getByText('Selecionar'))
    expect(screen.getByRole('button', { name: /excluir selecionadas/i })).toBeDisabled()
  })

  it('mostra o empty state quando nao ha datas', () => {
    renderSection({ rules: [] })
    expect(screen.getByText('Nenhum dia fixo cadastrado')).toBeInTheDocument()
    // Sem datas nao ha o que selecionar.
    expect(screen.queryByText('Selecionar')).not.toBeInTheDocument()
  })

  it('exclui uma faixa individual pelo botao do chip', async () => {
    const props = renderSection()
    await userEvent.click(screen.getByLabelText('Excluir horário 14:00 - 18:00 em 15/09/2026'))
    expect(props.onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 'r2' }))
  })

  it('desabilita o chip enquanto a exclusao esta em voo', () => {
    renderSection({ deletingIds: new Set(['r1']) })
    expect(screen.getByLabelText('Excluir horário 09:00 - 18:00 em 15/09/2026')).toBeDisabled()
  })
})
