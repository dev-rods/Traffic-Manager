import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DescontoField } from './DescontoField'
import { POLITICA_DA_CLINICA, SEM_DESCONTO, type DescontoEscolhido } from '@/lib/desconto'

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

  it('"Política da clínica" é o primeiro modo e explica o que a política decide (PRD 053)', () => {
    const { rerender } = render(<DescontoField valor={POLITICA_DA_CLINICA} onChange={vi.fn()} />)
    const botoes = screen.getAllByRole('button').map((b) => b.textContent)
    expect(botoes.slice(0, 4)).toEqual(['Política da clínica', 'Sem desconto', 'Parceria (100%)', 'Personalizado'])
    expect(screen.getByTestId('cotacao')).toHaveTextContent('Escolha a paciente e as áreas')

    rerender(<DescontoField valor={POLITICA_DA_CLINICA} onChange={vi.fn()} cotando />)
    expect(screen.getByTestId('cotacao')).toHaveTextContent('Consultando')

    rerender(
      <DescontoField
        valor={POLITICA_DA_CLINICA}
        onChange={vi.fn()}
        cotacao={{ originalPriceCents: 20000, discountPct: 15, discountReason: 'tier_2', finalPriceCents: 17000, areaCount: 3, isFirst: false }}
      />,
    )
    expect(screen.getByTestId('cotacao')).toHaveTextContent('2-4 áreas: 15% (-R$ 30,00)')

    rerender(
      <DescontoField
        valor={POLITICA_DA_CLINICA}
        onChange={vi.fn()}
        cotacao={{ originalPriceCents: 20000, discountPct: 0, discountReason: null, finalPriceCents: 20000, areaCount: 1, isFirst: false }}
      />,
    )
    expect(screen.getByTestId('cotacao')).toHaveTextContent('Sem desconto pela política')

    rerender(<DescontoField valor={POLITICA_DA_CLINICA} onChange={vi.fn()} cotacao={null} erroDaCotacao />)
    expect(screen.getByTestId('cotacao')).toHaveTextContent('Não foi possível consultar a política')
  })

  it('a cotação só aparece no modo política', () => {
    render(<DescontoField valor={SEM_DESCONTO} onChange={vi.fn()} cotando />)
    expect(screen.queryByTestId('cotacao')).not.toBeInTheDocument()
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
