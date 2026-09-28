import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgendaDoDia } from './AgendaDoDia'
import type { Appointment } from '@/types'

/**
 * A lista que substitui a grade em celular.
 *
 * O que ela precisa entregar, e a grade não entregava em 375px: ordem
 * cronológica óbvia, áreas e duração visíveis sem um toque a mais, e linhas
 * grandes o suficiente para o dedo.
 */
function agendamento(over: Partial<Appointment>): Appointment {
  return {
    id: Math.random().toString(),
    appointment_date: '2026-09-23',
    start_time: '09:00:00',
    end_time: '09:15:00',
    status: 'CONFIRMED',
    patient_name: 'Ana Clara',
    areas: 'Axilas',
    duration_minutes: 15,
    is_first_visit: false,
    ...over,
  } as Appointment
}

const clique = vi.fn()

describe('AgendaDoDia', () => {
  it('ordena por horário, e não pela ordem que veio da API', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '15:00:00', patient_name: 'Tarde' }),
          agendamento({ start_time: '09:00:00', patient_name: 'Manha' }),
          agendamento({ start_time: '11:30:00', patient_name: 'Meio' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    const nomes = screen.getAllByRole('button').map((b) => b.textContent)
    expect(nomes[0]).toContain('Manha')
    expect(nomes[1]).toContain('Meio')
    expect(nomes[2]).toContain('Tarde')
  })

  it('mostra áreas e duração sem exigir um toque', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ areas: 'Virilha Completa + ânus', duration_minutes: 25 })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText('Virilha Completa + ânus')).toBeInTheDocument()
    expect(screen.getByText(/25 min/)).toBeInTheDocument()
  })

  it('marca a duração ajustada à mão', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ duration_minutes: 10, manual_duration_minutes: 10 })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/ajustada/)).toBeInTheDocument()
  })

  it('só mostra o dia pedido', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ patient_name: 'Do dia' }),
          agendamento({ appointment_date: '2026-09-24', patient_name: 'De outro dia' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText('Do dia')).toBeInTheDocument()
    expect(screen.queryByText('De outro dia')).not.toBeInTheDocument()
  })

  it('cancelado não aparece, como na grade', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ status: 'CANCELLED', patient_name: 'Cancelada' })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText('Cancelada')).not.toBeInTheDocument()
    expect(screen.getByText(/Nenhum atendimento/)).toBeInTheDocument()
  })

  it('dia vazio explica, em vez de mostrar uma caixa em branco', () => {
    render(<AgendaDoDia dia="2026-09-23" appointments={[]} onAppointmentClick={clique} />)

    expect(screen.getByText(/Nenhum atendimento neste dia/)).toBeInTheDocument()
  })

  it('tocar na linha devolve o agendamento', async () => {
    const onClick = vi.fn()
    const alvo = agendamento({ patient_name: 'Larissa' })
    render(
      <AgendaDoDia dia="2026-09-23" appointments={[alvo]} onAppointmentClick={onClick} />,
    )

    await userEvent.click(screen.getByRole('button'))

    expect(onClick.mock.calls[0][0]).toBe(alvo)
  })
})

/**
 * Os vãos livres.
 *
 * Na grade do desktop o buraco se vê sozinho, como espaço em branco. Numa
 * lista de atendimentos ele some: descobrir que das 10h às 14h não há nada
 * exigia subtrair horários de cabeça, linha a linha.
 */
describe('AgendaDoDia - espaços livres', () => {
  function textos() {
    return Array.from(document.querySelectorAll('li')).map((l) =>
      l.textContent?.replace(/\s+/g, ' ').trim(),
    )
  }

  it('mostra o buraco entre dois atendimentos, no lugar certo da lista', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({
            start_time: '09:00:00', end_time: '10:00:00', patient_name: 'Manha',
          }),
          agendamento({
            start_time: '14:00:00', end_time: '15:00:00', patient_name: 'Tarde',
          }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    const linhas = textos()
    // o vão precisa cair ENTRE os dois: acima dele a lista voltaria no tempo
    expect(linhas[1]).toContain('Manha')
    expect(linhas[2]).toContain('Livre até 14:00')
    expect(linhas[2]).toContain('4h')
    expect(linhas[3]).toContain('Tarde')
  })

  it('diz quando o primeiro horário do dia abre', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '14:00:00', end_time: '15:00:00' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/Livre até 14:00/)).toBeInTheDocument()
  })

  it('não mostra vão que não comporta sessão', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '09:00:00', end_time: '10:00:00' }),
          agendamento({ start_time: '10:10:00', end_time: '11:00:00' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText(/Livre até 10:10/)).not.toBeInTheDocument()
  })

  it('cancelado abre o horário', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({
            start_time: '09:00:00', end_time: '10:00:00',
            status: 'CANCELLED', patient_name: 'Desmarcou',
          }),
          agendamento({ start_time: '14:00:00', end_time: '15:00:00' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText('Desmarcou')).not.toBeInTheDocument()
    // o horário do cancelado é absorvido: um vão das 7h às 14h, e não dois
    // vãos com a sessão desmarcada partindo a manhã ao meio
    expect(screen.getByText(/Livre até 14:00/)).toBeInTheDocument()
    expect(screen.queryByText(/Livre até 09:00/)).not.toBeInTheDocument()
  })

  it('vão não é clicável', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ start_time: '14:00:00', end_time: '15:00:00' })]}
        onAppointmentClick={clique}
      />,
    )

    // Só o atendimento é botão. O horário livre na tela não é horário
    // agendável: falta profissional, sala e duração, que só o servidor sabe.
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('dia sem atendimento continua mostrando o estado vazio', () => {
    render(<AgendaDoDia dia="2026-09-23" appointments={[]} onAppointmentClick={clique} />)

    expect(screen.getByText('Nenhum atendimento neste dia.')).toBeInTheDocument()
    expect(screen.queryByText(/Livre até/)).not.toBeInTheDocument()
  })
})
