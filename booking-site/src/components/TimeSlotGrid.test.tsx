import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TimeSlotGrid } from './TimeSlotGrid'

describe('TimeSlotGrid', () => {
  it('mostra o estado de carregamento', () => {
    render(<TimeSlotGrid slots={undefined} isLoading isError={false} selectedTime={null} onSelect={vi.fn()} />)
    expect(screen.getByLabelText('Carregando horários')).toBeInTheDocument()
  })

  it('mostra o estado de erro', () => {
    render(<TimeSlotGrid slots={undefined} isLoading={false} isError selectedTime={null} onSelect={vi.fn()} />)
    expect(screen.getByText(/não foi possível carregar/i)).toBeInTheDocument()
  })

  it('mostra o estado vazio quando não há horários', () => {
    render(<TimeSlotGrid slots={[]} isLoading={false} isError={false} selectedTime={null} onSelect={vi.fn()} />)
    expect(screen.getByText(/nenhum horário disponível/i)).toBeInTheDocument()
  })

  it('renderiza os horários e dispara onSelect ao clicar', async () => {
    const onSelect = vi.fn()
    render(
      <TimeSlotGrid slots={['10:00', '10:30']} isLoading={false} isError={false} selectedTime={null} onSelect={onSelect} />
    )
    await userEvent.click(screen.getByText('10:30'))
    expect(onSelect).toHaveBeenCalledWith('10:30')
  })
})
