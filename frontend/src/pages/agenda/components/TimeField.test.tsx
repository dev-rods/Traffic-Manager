import { useState } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TimeField } from './TimeField'

const SLOTS = ['07:45', '08:00', '08:15']

function monta(props: Partial<React.ComponentProps<typeof TimeField>> = {}) {
  const onChange = vi.fn()
  render(
    <TimeField
      value=""
      onChange={onChange}
      slots={SLOTS}
      loading={false}
      enabled
      {...props}
    />
  )
  return { onChange }
}

describe('TimeField', () => {
  beforeEach(() => vi.clearAllMocks())

  it('mostra os horários sugeridos', () => {
    monta()
    for (const slot of SLOTS) {
      expect(screen.getByRole('button', { name: slot })).toBeInTheDocument()
    }
  })

  it('clicar num sugerido escolhe o horário', async () => {
    const { onChange } = monta()

    await userEvent.click(screen.getByRole('button', { name: '08:00' }))

    expect(onChange).toHaveBeenCalledWith('08:00')
  })

  // O ponto da feature: antes só dava para escolher entre os sugeridos.
  //
  // Precisa de estado de verdade. Com `value` fixo e onChange mockado, cada
  // tecla parte de "" outra vez e o campo nunca chega ao horário completo -
  // o teste mediria o dublê, não o componente.
  it('dá para digitar um horário fora da lista', async () => {
    function Controlado() {
      const [time, setTime] = useState('')
      return (
        <>
          <TimeField value={time} onChange={setTime} slots={SLOTS} enabled />
          <output data-testid="escolhido">{time}</output>
        </>
      )
    }
    render(<Controlado />)

    await userEvent.type(screen.getByLabelText('Horário manual'), '19:30')

    expect(screen.getByTestId('escolhido')).toHaveTextContent('19:30')
    expect(screen.getByText('Fora dos horários sugeridos')).toBeInTheDocument()
  })

  it('avisa quando o horário está fora dos sugeridos', () => {
    monta({ value: '19:30' })

    expect(screen.getByText('Fora dos horários sugeridos')).toBeInTheDocument()
  })

  it('não avisa quando o horário é um dos sugeridos', () => {
    monta({ value: '08:00' })

    expect(screen.queryByText('Fora dos horários sugeridos')).not.toBeInTheDocument()
  })

  // O aviso é informativo: quem digitou fora da lista quase sempre sabe o que
  // está fazendo. Bloquear tiraria a razão de a feature existir.
  it('o aviso não desabilita nada', () => {
    monta({ value: '19:30' })

    expect(screen.getByLabelText('Horário manual')).not.toBeDisabled()
  })

  it('sem data ou serviço, não pede horário', () => {
    monta({ enabled: false })

    expect(screen.getByText(/Selecione data e serviço/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Horário manual')).not.toBeInTheDocument()
  })

  it('carregando não mostra sugestão nem esconde o campo manual', () => {
    monta({ loading: true })

    expect(screen.queryByRole('button', { name: '08:00' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Horário manual')).toBeInTheDocument()
  })

  // O dia sem grade é justamente quando a atendente mais precisa digitar.
  it('sem horários sugeridos, o campo manual continua disponível', () => {
    monta({ slots: [] })

    expect(screen.getByLabelText('Horário manual')).toBeInTheDocument()
    expect(screen.getByText(/Digite abaixo se quiser marcar mesmo assim/)).toBeInTheDocument()
  })
})
