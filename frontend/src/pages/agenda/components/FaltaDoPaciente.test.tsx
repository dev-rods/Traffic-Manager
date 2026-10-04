import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppointmentPopover } from './AppointmentPopover'
import { AgendaDoDia } from './AgendaDoDia'
import type { Appointment, AvailabilityRule } from '@/types'

/**
 * Falta (`NO_SHOW`) é diferente de cancelamento, e a agenda tem de mostrar isso.
 *
 * Quem cancela com antecedência libera o horário; quem não aparece queima o
 * horário. Até 04/10/2026 os dois viravam `CANCELLED` e a diferença se perdia -
 * e a conversão offline depende dela, porque afirma uma COMPRA ao Google Ads.
 *
 * Duas decisões de UX que estes testes travam:
 *
 * 1. **A falta aparece na agenda**, ao contrário do cancelado (que os dois
 *    componentes filtram). Não é só fidelidade histórica: é pelo card que se
 *    alcança "Desmarcar falta". Filtrar deixaria o desfazer inalcançável.
 * 2. **Marcar falta não abre modal.** A confirmação se paga quando a ação é
 *    irreversível - cancelar é, falta não.
 */

const HOJE = new Date()
const iso = (d: Date) =>
  [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')

const ONTEM = iso(new Date(HOJE.getTime() - 86400000))
const AMANHA = iso(new Date(HOJE.getTime() + 86400000))

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    appointment_date: ONTEM,
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

function montaPopover(over: Partial<Appointment> = {}) {
  const props = {
    onClose: vi.fn(),
    onEdit: vi.fn(),
    onCancel: vi.fn(),
    onMarcarFalta: vi.fn(),
    onDesmarcarFalta: vi.fn(),
  }
  render(
    <AppointmentPopover
      appointment={agendamento(over)}
      anchorRect={{ top: 0, right: 0 } as DOMRect}
      {...props}
    />,
  )
  return props
}

describe('a ação de marcar falta', () => {
  it('aparece quando a sessão já passou', () => {
    montaPopover({ appointment_date: ONTEM })

    expect(screen.getByText('Marcar falta')).toBeInTheDocument()
  })

  it('NÃO aparece em sessão futura', () => {
    // Não há falta a marcar no que ainda vai acontecer, e oferecer o botão ali
    // faria a atendente descobrir pelo erro do servidor que não se aplicava.
    montaPopover({ appointment_date: AMANHA })

    expect(screen.queryByText('Marcar falta')).not.toBeInTheDocument()
  })

  it('NÃO aparece na sessão de hoje', () => {
    // O backend usa `appointment_date < CURRENT_DATE`: o dia de hoje ainda está
    // acontecendo. A tela tem de concordar com o servidor, senão o botão existe
    // e o pedido volta com erro.
    montaPopover({ appointment_date: iso(HOJE) })

    expect(screen.queryByText('Marcar falta')).not.toBeInTheDocument()
  })

  it('chama onMarcarFalta sem passar por modal', () => {
    const props = montaPopover({ appointment_date: ONTEM })

    screen.getByText('Marcar falta').click()

    expect(props.onMarcarFalta).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'a1' }),
    )
  })
})

describe('a ação de desmarcar falta', () => {
  it('aparece quando o agendamento está em falta', () => {
    montaPopover({ status: 'NO_SHOW' })

    expect(screen.getByText('Desmarcar falta')).toBeInTheDocument()
  })

  it('não aparece em agendamento confirmado', () => {
    montaPopover({ status: 'CONFIRMED' })

    expect(screen.queryByText('Desmarcar falta')).not.toBeInTheDocument()
  })

  it('em falta, o resto das ações sai de cena', () => {
    // A sessão passou e a pessoa não veio: editar e registrar sessão não se
    // aplicam, e cancelar perderia justamente a informação da falta. Sobra
    // corrigir o registro.
    montaPopover({ status: 'NO_SHOW' })

    expect(screen.queryByText('Editar agendamento')).not.toBeInTheDocument()
    expect(screen.queryByText('Cancelar agendamento')).not.toBeInTheDocument()
    expect(screen.getByText('Desmarcar falta')).toBeInTheDocument()
  })

  it('chama onDesmarcarFalta', () => {
    const props = montaPopover({ status: 'NO_SHOW' })

    screen.getByText('Desmarcar falta').click()

    expect(props.onDesmarcarFalta).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'a1' }),
    )
  })
})

describe('a falta na lista do dia', () => {
  const regra: AvailabilityRule = {
    id: 'r1',
    clinic_id: 'clinica-1',
    day_of_week: null,
    rule_date: ONTEM,
    start_time: '08:00:00',
    end_time: '20:00:00',
    professional_id: null,
    active: true,
  }

  function monta(status: Appointment['status']) {
    render(
      <AgendaDoDia
        dia={ONTEM}
        appointments={[agendamento({ status, patient_name: 'Ana Clara' })]}
        rules={[regra]}
        onAppointmentClick={vi.fn()}
      />,
    )
  }

  it('continua visível, ao contrário do cancelado', () => {
    monta('NO_SHOW')

    expect(screen.getByText('Ana Clara')).toBeInTheDocument()
  })

  it('o cancelado segue filtrado', () => {
    // Confirma o contraste: o motivo de a falta aparecer é ela ser diferente
    // de cancelamento, não uma mudança de regra para os dois.
    monta('CANCELLED')

    expect(screen.queryByText('Ana Clara')).not.toBeInTheDocument()
  })

  it('traz o marcador FALTOU, e não só uma cor', () => {
    // Cor sozinha não basta: quem tem daltonismo, ou olha a agenda no celular
    // sob sol, precisa distinguir também.
    monta('NO_SHOW')

    expect(screen.getByText('FALTOU')).toBeInTheDocument()
  })

  it('o confirmado não traz o marcador', () => {
    monta('CONFIRMED')

    expect(screen.queryByText('FALTOU')).not.toBeInTheDocument()
  })

  it('risca o nome de quem faltou', () => {
    monta('NO_SHOW')

    expect(screen.getByText('Ana Clara').className).toContain('line-through')
  })
})
