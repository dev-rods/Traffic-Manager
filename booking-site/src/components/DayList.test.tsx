import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DayList } from './DayList'
import type { AvailabilityWindow, DayAvailability } from '@/types'

const WINDOW: AvailabilityWindow = { start: '2026-10-28', end: '2026-10-31', nextOpensOn: '2026-11-01' }

const DAYS: Record<string, DayAvailability> = {
  '2026-10-28': { status: 'AVAILABLE', slots: ['09:00'] },
  '2026-10-29': { status: 'FULL', slots: [] },
  '2026-10-30': { status: 'CLOSED', slots: [] },
  '2026-10-31': { status: 'AVAILABLE', slots: ['10:00'] },
}

function renderList(props: Partial<Parameters<typeof DayList>[0]> = {}) {
  const onSelectDate = vi.fn()
  const onRetry = vi.fn()
  render(
    <DayList
      days={DAYS}
      bookingWindow={WINDOW}
      isLoading={false}
      isError={false}
      onRetry={onRetry}
      selectedDate={null}
      onSelectDate={onSelectDate}
      clinicPhone="11999990000"
      {...props}
    />
  )
  return { onSelectDate, onRetry }
}

describe('DayList', () => {
  it('mostra só os dias com horário — lotado e fechado nem aparecem', () => {
    renderList()
    expect(screen.getByRole('button', { name: 'QUA 28 de outubro' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'SÁB 31 de outubro' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /29 de outubro/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /30 de outubro/ })).not.toBeInTheDocument()
  })

  it('seleciona o dia', async () => {
    const { onSelectDate } = renderList({ selectedDate: '2026-10-31' })
    expect(screen.getByRole('button', { name: 'SÁB 31 de outubro' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'QUA 28 de outubro' }))
    expect(onSelectDate).toHaveBeenCalledWith('2026-10-28')
  })

  it('mês sem vaga explica quando o próximo abre e oferece contato', () => {
    renderList({ days: { '2026-10-29': { status: 'FULL', slots: [] } } })
    expect(screen.getByText('Não há mais horários disponíveis em outubro.')).toBeInTheDocument()
    expect(screen.getByText('A agenda de novembro abre em 01/11.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Falar com a clínica/ })).toHaveAttribute(
      'href',
      'https://wa.me/5511999990000'
    )
  })

  it('sem telefone da clínica não mostra o botão de contato', () => {
    renderList({ days: {}, clinicPhone: null })
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('carregando e erro com nova tentativa', async () => {
    const { onRetry } = renderList({ isLoading: false, isError: true })
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('skeleton enquanto carrega', () => {
    renderList({ isLoading: true, days: undefined })
    expect(screen.getByLabelText('Carregando datas')).toBeInTheDocument()
  })
})
