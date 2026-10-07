import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WeekGrid } from './WeekGrid'
import type { Appointment } from '@/types'

/**
 * A expansão de um dia é feita de fiação: a AgendaPage passa um array de UM
 * elemento e o grid, que já desenha `weekDays.length` colunas, resolve o resto.
 *
 * O que pode quebrar sem ninguém perceber é justamente a fiação - o cabeçalho
 * deixar de ser clicável, ou a saída não aparecer e o usuário ficar preso num
 * dia só. É isso que este arquivo trava.
 */

const SEM_AGENDAMENTOS: Appointment[] = []

function renderizar(props: Partial<Parameters<typeof WeekGrid>[0]> = {}) {
  return render(
    <WeekGrid
      weekDays={['2026-09-21', '2026-09-22', '2026-09-23']}
      appointments={SEM_AGENDAMENTOS}
      onSlotClick={vi.fn()}
      onAppointmentClick={vi.fn()}
      {...props}
    />,
  )
}

describe('WeekGrid: expansão de um dia', () => {
  it('clicar no cabeçalho avisa qual dia foi escolhido', async () => {
    const onDayClick = vi.fn()
    renderizar({ onDayClick })

    await userEvent.click(screen.getByRole('button', { name: /22/ }))

    expect(onDayClick).toHaveBeenCalledWith('2026-09-22')
  })

  it('sem onDayClick o cabeçalho não vira botão', () => {
    renderizar()

    // Sobram os botões de slot, mas nenhum com o rótulo do dia.
    expect(screen.queryByRole('button', { name: /22/ })).not.toBeInTheDocument()
  })

  it('um dia só ocupa a largura inteira', () => {
    const { container } = renderizar({ weekDays: ['2026-09-23'], expandido: true })

    const grid = container.querySelector('[style*="grid-template-columns"]') as HTMLElement
    expect(grid.style.gridTemplateColumns).toBe('52px repeat(1, 1fr)')
  })

  it('expandido mostra a saída, e ela fica no próprio cabeçalho', async () => {
    const onDayClick = vi.fn()
    renderizar({ weekDays: ['2026-09-23'], expandido: true, onDayClick })

    expect(screen.getByText('‹ todos os dias')).toBeInTheDocument()

    // A saída é o mesmo alvo da entrada: clicar de novo volta.
    await userEvent.click(screen.getByRole('button', { name: /todos os dias/ }))
    expect(onDayClick).toHaveBeenCalledWith('2026-09-23')
  })

  it('fechado não anuncia uma saída que não existe', () => {
    renderizar({ onDayClick: vi.fn() })

    expect(screen.queryByText('‹ todos os dias')).not.toBeInTheDocument()
  })
})

describe('WeekGrid: a caixa usa a largura que tem', () => {
  const COM_AREA: Appointment[] = [
    {
      id: 'a1',
      appointment_date: '2026-09-23',
      start_time: '09:00:00',
      end_time: '09:15:00',
      status: 'CONFIRMED',
      patient_name: 'Ana Clara',
      areas: 'Virilha Completa + ânus',
      is_first_visit: false,
    } as Appointment,
  ]

  it('expandido, a área entra ao lado do nome', () => {
    renderizar({ weekDays: ['2026-09-23'], expandido: true, appointments: COM_AREA })

    expect(screen.getByText(/Virilha Completa \+ ânus/)).toBeInTheDocument()
  })

  it('na semana, só horário e nome - a área não cabe em coluna estreita', () => {
    renderizar({ appointments: COM_AREA })

    expect(screen.getByText(/Ana Clara/)).toBeInTheDocument()
    expect(screen.queryByText(/Virilha Completa \+ ânus/)).not.toBeInTheDocument()
  })
})
