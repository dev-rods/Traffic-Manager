import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AcoesEmLote } from './AcoesEmLote'

/**
 * O defeito que este arquivo existe para impedir: a régua estava posicionada
 * com `left-56`, os 224px da sidebar do desktop. Em celular a sidebar virou
 * drawer e deixou de ocupar lugar, então o recuo empurrava a régua para fora
 * de uma tela de 375px.
 *
 * Ela renderizava. Passava em qualquer teste de "existe na tela". Só não era
 * visível - e a seleção em lote virava um recurso sem saída no celular.
 */
afterEach(cleanup)

function renderiza(quantidade = 2, acoes: Record<string, () => void> = {}) {
  return render(
    <AcoesEmLote
      quantidade={quantidade}
      onLimpar={acoes.onLimpar ?? vi.fn()}
      onWhatsApp={acoes.onWhatsApp ?? vi.fn()}
      onExcluir={acoes.onExcluir ?? vi.fn()}
    />,
  )
}

describe('AcoesEmLote', () => {
  it('sem seleção não aparece', () => {
    const { container } = renderiza(0)

    expect(container).toBeEmptyDOMElement()
  })

  it('o recuo da sidebar só vale de md para cima', () => {
    // ESTE é o teste do bug. `left-0` no celular, `md:left-56` no desktop.
    const { container } = renderiza()
    const regua = container.firstElementChild as HTMLElement

    expect(regua.className).toContain('left-0')
    expect(regua.className).toContain('md:left-56')
    // Sem o prefixo, o recuo volta a empurrar a régua para fora.
    expect(regua.className).not.toMatch(/(^|\s)left-56/)
  })

  it('conta no singular e no plural', () => {
    renderiza(1)
    expect(screen.getByText('1 paciente selecionado')).toBeInTheDocument()
    cleanup()

    renderiza(3)
    expect(screen.getByText('3 pacientes selecionados')).toBeInTheDocument()
  })

  it('as três ações respondem', async () => {
    const onLimpar = vi.fn()
    const onWhatsApp = vi.fn()
    const onExcluir = vi.fn()
    renderiza(2, { onLimpar, onWhatsApp, onExcluir })

    await userEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    await userEvent.click(screen.getByRole('button', { name: /Excluir/ }))
    await userEvent.click(screen.getByRole('button', { name: /Limpar/ }))

    expect(onWhatsApp).toHaveBeenCalledOnce()
    expect(onExcluir).toHaveBeenCalledOnce()
    expect(onLimpar).toHaveBeenCalledOnce()
  })

  it('os botões têm alvo de toque', () => {
    // `size="sm"` dá ~28px, desenhado para mouse. 44px é a régua do CLAUDE.md.
    renderiza()

    for (const nome of [/WhatsApp/, /Excluir/, /Limpar/]) {
      expect(screen.getByRole('button', { name: nome }).className).toContain('min-h-11')
    }
  })

  it('limpar continua alcançável por leitor de tela em celular', () => {
    // No celular o rótulo vira um "x" visual; sem o texto acessível, o botão
    // ficaria sem nome nenhum para quem não enxerga.
    renderiza()

    expect(screen.getByRole('button', { name: 'Limpar seleção' })).toBeInTheDocument()
  })
})
