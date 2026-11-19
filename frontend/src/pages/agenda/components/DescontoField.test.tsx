import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DescontoField } from './DescontoField'
import { SEM_DESCONTO, type DescontoEscolhido } from '@/lib/desconto'

const custom = (over: Partial<DescontoEscolhido> = {}): DescontoEscolhido => ({
  modo: 'custom',
  tipo: 'pct',
  texto: '',
  ...over,
})

describe('DescontoField', () => {
  it('sem desconto não mostra o campo', () => {
    render(<DescontoField valor={SEM_DESCONTO} onChange={vi.fn()} />)
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('"Personalizado" abre o seletor % / R$ e o campo em porcento', async () => {
    const onChange = vi.fn()
    render(<DescontoField valor={SEM_DESCONTO} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: 'Personalizado' }))

    expect(onChange).toHaveBeenCalledWith({ ...SEM_DESCONTO, modo: 'custom' })
  })

  it('trocar para R$ limpa o texto: 20% e R$ 20 são descontos diferentes', async () => {
    const onChange = vi.fn()
    render(<DescontoField valor={custom({ texto: '20' })} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: 'R$' }))

    expect(onChange).toHaveBeenCalledWith(custom({ tipo: 'cents', texto: '' }))
  })

  it('clicar no tipo já escolhido não mexe em nada', async () => {
    const onChange = vi.fn()
    render(<DescontoField valor={custom({ texto: '20' })} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: '%' }))

    expect(onChange).not.toHaveBeenCalled()
  })

  it('campo em branco não acusa erro: isso é do submit', () => {
    render(<DescontoField valor={custom()} onChange={vi.fn()} subtotalCents={19500} />)
    expect(screen.queryByText(/Informe/)).not.toBeInTheDocument()
  })

  it('reais acima do subtotal acusam na hora', () => {
    render(
      <DescontoField valor={custom({ tipo: 'cents', texto: '250' })} onChange={vi.fn()} subtotalCents={19500} />,
    )
    expect(screen.getByText('O desconto não pode passar do valor da sessão.')).toBeInTheDocument()
  })

  it('três casas decimais acusam', () => {
    render(<DescontoField valor={custom({ texto: '12,555' })} onChange={vi.fn()} />)
    expect(screen.getByText(/até duas casas/)).toBeInTheDocument()
  })

  it('o campo aceita vírgula e repassa o texto como está', async () => {
    const onChange = vi.fn()
    render(<DescontoField valor={custom()} onChange={onChange} />)

    await userEvent.type(screen.getByLabelText('Desconto em porcento'), ',')

    expect(onChange).toHaveBeenCalledWith(custom({ texto: ',' }))
  })
})
