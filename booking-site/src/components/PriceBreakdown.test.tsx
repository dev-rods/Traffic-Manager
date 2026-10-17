import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PriceBreakdown } from './PriceBreakdown'
import type { Quote } from '@/types'

const BASE: Quote = {
  originalPriceCents: 20000,
  discountPct: 0,
  discountReason: null,
  finalPriceCents: 20000,
  areaCount: 1,
  combos: [],
}

// Intl separa "R$" do número com espaço inseparável.
const brl = (texto: string) => new RegExp(texto.replace(/\s/g, '\\s').replace('$', '\\$'))

describe('PriceBreakdown', () => {
  it('sem desconto mostra só o total', () => {
    render(<PriceBreakdown quote={BASE} isLoading={false} isError={false} />)
    expect(screen.getByText('Total')).toBeInTheDocument()
    expect(screen.getByText(brl('R$ 200,00'))).toBeInTheDocument()
    expect(screen.queryByText(/Desconto/)).not.toBeInTheDocument()
    expect(screen.queryByText('Valor final')).not.toBeInTheDocument()
  })

  it('com desconto mostra total, desconto com o motivo e valor final', () => {
    render(
      <PriceBreakdown
        quote={{ ...BASE, discountPct: 50, discountReason: 'first_session', finalPriceCents: 10000 }}
        isLoading={false}
        isError={false}
      />
    )
    expect(screen.getByText(/Desconto · Primeira sessão \(50%\)/)).toBeInTheDocument()
    expect(screen.getByText(brl('− R$ 100,00'))).toBeInTheDocument()
    expect(screen.getByText('Valor final')).toBeInTheDocument()
    expect(screen.getByText(brl('R$ 200,00'))).toHaveClass('line-through')
  })

  it('percentual fracionado em formato brasileiro', () => {
    render(
      <PriceBreakdown
        quote={{ ...BASE, discountPct: 12.5, discountReason: 'personalizado', finalPriceCents: 17500 }}
        isLoading={false}
        isError={false}
      />
    )
    expect(screen.getByText(/Desconto especial \(12,5%\)/)).toBeInTheDocument()
  })

  it('explica o combo aplicado', () => {
    render(
      <PriceBreakdown
        quote={{ ...BASE, combos: [{ from: ['Virilha', 'Perianal'], to: 'Virilha + ânus', savingsCents: 7500 }] }}
        isLoading={false}
        isError={false}
      />
    )
    expect(screen.getByText(/Virilha \+ Perianal viraram o combo/)).toBeInTheDocument()
    expect(screen.getByText(brl('economia de R$ 75,00'))).toBeInTheDocument()
  })

  it('sem preço cadastrado não inventa R$ 0', () => {
    render(
      <PriceBreakdown
        quote={{ ...BASE, originalPriceCents: null, finalPriceCents: null }}
        isLoading={false}
        isError={false}
      />
    )
    expect(screen.getByText('Valor a combinar na clínica')).toBeInTheDocument()
  })

  it('carregando e erro', () => {
    const { rerender } = render(<PriceBreakdown quote={undefined} isLoading isError={false} />)
    expect(screen.getByLabelText('Calculando valor')).toBeInTheDocument()
    rerender(<PriceBreakdown quote={undefined} isLoading={false} isError />)
    expect(screen.getByText('Não foi possível calcular o valor agora.')).toBeInTheDocument()
  })
})
