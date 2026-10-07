import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgendaDoDia } from './AgendaDoDia'
import type { Appointment, AvailabilityRule } from '@/types'

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

/**
 * O horário real da clínica no dia. Sem regra, a lista não mostra vão nenhum -
 * então os testes que exercitam vãos precisam de uma.
 */
function regra(over: Partial<AvailabilityRule> = {}): AvailabilityRule {
  return {
    id: Math.random().toString(),
    clinic_id: 'clinica-1',
    day_of_week: null,
    rule_date: '2026-09-23',
    start_time: '08:00:00',
    end_time: '20:00:00',
    professional_id: null,
    active: true,
    ...over,
  }
}

const EXPEDIENTE = [regra()]

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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText('Cancelada')).not.toBeInTheDocument()
    expect(screen.getByText(/Nenhum atendimento/)).toBeInTheDocument()
  })

  it('dia vazio explica, em vez de mostrar uma caixa em branco', () => {
    render(<AgendaDoDia
        dia="2026-09-23"
        appointments={[]}
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />)

    expect(screen.getByText(/Nenhum atendimento neste dia/)).toBeInTheDocument()
  })

  it('tocar na linha devolve o agendamento', async () => {
    const onClick = vi.fn()
    const alvo = agendamento({ patient_name: 'Larissa' })
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[alvo]}
        rules={EXPEDIENTE}
        onAppointmentClick={onClick}
      />,
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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/Livre até 14:00/)).toBeInTheDocument()
  })

  it('mostra vão de 10 minutos entre dois atendimentos', () => {
    // Regressão relatada em 28/09/2026 sobre a agenda de 29/09: o buraco
    // entre um atendimento que terminava 17:20 e o seguinte, às 17:30, não
    // aparecia. O piso era 15 minutos - a granularidade da GRADE - enquanto a
    // clínica marca 34 sessões de 10 minutos e 13 de 5.
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '16:45:00', end_time: '17:20:00' }),
          agendamento({ start_time: '17:30:00', end_time: '17:40:00' }),
        ]}
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/Livre até 17:30/)).toBeInTheDocument()
  })

  it('não mostra vão que não comporta sessão', () => {
    // 3 minutos: não existe sessão desse tamanho na clínica
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '09:00:00', end_time: '10:00:00' }),
          agendamento({ start_time: '10:03:00', end_time: '11:00:00' }),
        ]}
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText(/Livre até 10:03/)).not.toBeInTheDocument()
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
        rules={EXPEDIENTE}
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
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />,
    )

    // Só o atendimento é botão. O horário livre na tela não é horário
    // agendável: falta profissional, sala e duração, que só o servidor sabe.
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('dia sem atendimento continua mostrando o estado vazio', () => {
    render(<AgendaDoDia
        dia="2026-09-23"
        appointments={[]}
        rules={EXPEDIENTE}
        onAppointmentClick={clique}
      />)

    expect(screen.getByText('Nenhum atendimento neste dia.')).toBeInTheDocument()
    expect(screen.queryByText(/Livre até/)).not.toBeInTheDocument()
  })
})

describe('AgendaDoDia - horário real da clínica', () => {
  it('fecha no horário da clínica, não às 22h', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ start_time: '09:00:00', end_time: '10:00:00' })]}
        rules={[regra({ start_time: '08:00:00', end_time: '19:00:00' })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/Livre até 19:00/)).toBeInTheDocument()
    expect(screen.queryByText(/Livre até 22:00/)).not.toBeInTheDocument()
  })

  it('abre no horário da clínica, não às 7h', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ start_time: '14:00:00', end_time: '15:00:00' })]}
        rules={[regra({ start_time: '10:00:00', end_time: '19:00:00' })]}
        onAppointmentClick={clique}
      />,
    )

    const linhas = Array.from(document.querySelectorAll('li')).map((l) =>
      l.textContent?.replace(/\s+/g, ' ').trim(),
    )
    // o vão começa às 10:00, e não às 07:00
    expect(linhas[0]).toContain('10:00')
    expect(linhas[0]).toContain('Livre até 14:00')
  })

  it('sem regra para o dia, não oferece horário nenhum', () => {
    // Inventar um fechamento seria oferecer horário que a clínica não atende.
    // Os atendimentos continuam aparecendo: eles existem de qualquer forma.
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ patient_name: 'Ana Clara' })]}
        rules={[]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText('Ana Clara')).toBeInTheDocument()
    expect(screen.queryByText(/Livre até/)).not.toBeInTheDocument()
  })

  it('atendimento fora do expediente não gera vão negativo', () => {
    // Encaixe às 19h30 numa clínica que fecha às 19h: acontece.
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ start_time: '19:30:00', end_time: '20:00:00' })]}
        rules={[regra({ start_time: '08:00:00', end_time: '19:00:00' })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/Livre até 19:00/)).toBeInTheDocument()
    expect(screen.getAllByText(/Livre até/)).toHaveLength(1)
  })
})
