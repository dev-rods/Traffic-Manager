import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Drawer } from './Drawer'
import { Modal } from './Modal'

/**
 * O contrato do painel lateral, do ponto de vista de quem está com o celular
 * na mão: abre, dá para sair de três jeitos, e o fundo não rola por baixo.
 */
afterEach(cleanup)

describe('Drawer', () => {
  it('fechado não renderiza nada', () => {
    render(<Drawer open={false} onClose={vi.fn()} title="Menu">conteudo</Drawer>)

    expect(screen.queryByText('conteudo')).not.toBeInTheDocument()
  })

  it('aberto mostra título e conteúdo', () => {
    render(<Drawer open onClose={vi.fn()} title="Menu">conteudo</Drawer>)

    expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument()
    expect(screen.getByText('conteudo')).toBeInTheDocument()
  })

  it('o X fecha', async () => {
    const onClose = vi.fn()
    render(<Drawer open onClose={onClose} title="Menu">c</Drawer>)

    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(onClose).toHaveBeenCalled()
  })

  it('Esc fecha', async () => {
    const onClose = vi.fn()
    render(<Drawer open onClose={onClose} title="Menu">c</Drawer>)

    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalled()
  })

  it('entra pelo lado pedido', () => {
    const { container, unmount } = render(
      <Drawer open onClose={vi.fn()} title="Menu" side="right">c</Drawer>,
    )
    expect(container.querySelector('aside')?.className).toContain('right-0')
    unmount()

    const { container: c2 } = render(
      <Drawer open onClose={vi.fn()} title="Menu">c</Drawer>,
    )
    expect(c2.querySelector('aside')?.className).toContain('left-0')
  })
})

describe('a trava de rolagem do fundo', () => {
  it('trava enquanto aberto e destrava ao fechar', () => {
    const { unmount } = render(<Drawer open onClose={vi.fn()} title="M">c</Drawer>)
    expect(document.body.style.overflow).toBe('hidden')

    unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('com um modal SOBRE um drawer, o primeiro a fechar não destrava', () => {
    // Sem o contador em useOverlayLock, fechar o modal devolveria a rolagem ao
    // fundo com o drawer ainda por cima - e a tela rolaria atrás dele.
    const drawer = render(<Drawer open onClose={vi.fn()} title="M">c</Drawer>)
    const modal = render(<Modal open onClose={vi.fn()} title="Janela">c</Modal>)

    expect(document.body.style.overflow).toBe('hidden')

    modal.unmount()
    expect(document.body.style.overflow).toBe('hidden')

    drawer.unmount()
    expect(document.body.style.overflow).toBe('')
  })
})
