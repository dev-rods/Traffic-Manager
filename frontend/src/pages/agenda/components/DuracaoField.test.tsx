import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DuracaoField } from './DuracaoField'

/**
 * O contrato do campo, do ponto de vista de quem está na recepção.
 *
 * O risco caro aqui não é visual: é a atendente achar que mudou a regra da
 * clínica ao mexer num agendamento. Por isso o texto "vale só para este
 * agendamento" é testado como comportamento, não tratado como enfeite.
 */
describe('DuracaoField', () => {
  it('mostra a duração calculada quando ninguém fixou nada', () => {
    render(<DuracaoField calculada={30} manual={null} onChange={vi.fn()} />)

    expect(screen.getByText('30 minutos')).toBeInTheDocument()
    expect(screen.getByText('calculada pelas áreas')).toBeInTheDocument()
  })

  it('"Ajustar" começa do valor calculado, não do zero', async () => {
    const onChange = vi.fn()
    render(<DuracaoField calculada={30} manual={null} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: 'Ajustar' }))

    expect(onChange).toHaveBeenCalledWith(30)
  })

  it('com duração fixada, diz quanto a regra calcularia', () => {
    render(<DuracaoField calculada={30} manual={75} onChange={vi.fn()} />)

    expect(screen.getByRole('spinbutton')).toHaveValue(75)
    expect(screen.getByText(/A regra calcula 30 min/)).toBeInTheDocument()
  })

  it('deixa explícito que vale só para este agendamento', () => {
    render(<DuracaoField calculada={30} manual={75} onChange={vi.fn()} />)

    expect(screen.getByText(/Vale só para este agendamento/)).toBeInTheDocument()
  })

  it('"Voltar ao cálculo" manda null, que é o que solta o override', async () => {
    const onChange = vi.fn()
    render(<DuracaoField calculada={30} manual={75} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: 'Voltar ao cálculo' }))

    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('avisa quando o valor fixado foi descartado por troca de áreas', () => {
    render(
      <DuracaoField calculada={30} manual={null} onChange={vi.fn()} avisoDeDescarte />
    )

    expect(
      screen.getByText(/descartada porque as áreas mudaram/)
    ).toBeInTheDocument()
  })

  it('acusa valor fora da faixa antes de a atendente salvar', () => {
    render(<DuracaoField calculada={30} manual={600} onChange={vi.fn()} />)

    expect(screen.getByText(/precisa estar entre 5 e 480/)).toBeInTheDocument()
  })

  it('não acusa nada dentro da faixa', () => {
    render(<DuracaoField calculada={30} manual={75} onChange={vi.fn()} />)

    expect(screen.queryByText(/precisa estar entre/)).not.toBeInTheDocument()
  })

  it('sem áreas escolhidas, não inventa uma duração', () => {
    render(<DuracaoField manual={null} onChange={vi.fn()} />)

    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ajustar' })).not.toBeInTheDocument()
  })
})
