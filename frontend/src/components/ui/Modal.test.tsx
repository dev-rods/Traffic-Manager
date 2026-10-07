import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from './Modal'

/**
 * A janela compartilhada por 13 telas.
 *
 * O que estes testes protegem é o **desktop**: a variante de tela cheia entrou
 * por celular, e um `max-w` perdido no caminho espalharia a mudança por todas
 * as treze de uma vez, sem ninguém pedir.
 */
afterEach(cleanup)

function corpoDaJanela(container: HTMLElement) {
  // O filho direto do overlay é a janela em si.
  return container.firstElementChild?.firstElementChild as HTMLElement
}

describe('Modal', () => {
  it('fechado não renderiza', () => {
    render(<Modal open={false} onClose={vi.fn()} title="T">conteudo</Modal>)

    expect(screen.queryByText('conteudo')).not.toBeInTheDocument()
  })

  it('mostra título e conteúdo', () => {
    render(<Modal open onClose={vi.fn()} title="Novo registro">conteudo</Modal>)

    expect(screen.getByText('Novo registro')).toBeInTheDocument()
    expect(screen.getByText('conteudo')).toBeInTheDocument()
  })

  it('Esc e o X fecham', async () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose} title="T">c</Modal>)

    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('a largura do desktop continua presa ao breakpoint', () => {
    // `md:max-w-lg` e não `max-w-lg`: sem o prefixo, o celular herdaria a
    // largura de 512px e a tela cheia não existiria.
    const { container } = render(
      <Modal open onClose={vi.fn()} title="T" width="lg">c</Modal>,
    )

    const janela = corpoDaJanela(container)
    expect(janela.className).toContain('md:max-w-lg')
    expect(janela.className).not.toMatch(/(^|\s)max-w-lg/)
  })

  it('em celular ocupa a tela toda; de md para cima volta a ser caixa', () => {
    const { container } = render(<Modal open onClose={vi.fn()} title="T">c</Modal>)

    const janela = corpoDaJanela(container)
    // Altura cheia por padrão, e só `md` traz de volta o canto arredondado e o
    // teto de altura.
    expect(janela.className).toContain('h-full')
    expect(janela.className).toContain('md:h-auto')
    expect(janela.className).toContain('md:rounded-xl')
  })

  it('o X tem alvo de toque, e não só de mouse', () => {
    render(<Modal open onClose={vi.fn()} title="T">c</Modal>)

    // 44px é a régua do CLAUDE.md. `h-11` = 44px.
    expect(screen.getByRole('button', { name: 'Fechar' }).className).toContain('h-11')
  })
})
