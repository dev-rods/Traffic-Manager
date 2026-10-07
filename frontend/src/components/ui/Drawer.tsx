import { useRef } from 'react'
import { useOverlayLock } from '@/hooks/useOverlayLock'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  /** De que lado ele entra. Menu à esquerda, filtros à direita. */
  side?: 'left' | 'right'
  children: React.ReactNode
}

/**
 * Painel que entra pela lateral, por cima do conteúdo.
 *
 * Nasceu servindo a dois casos que são a mesma interação: o menu lateral em
 * celular (hoje uma barra fixa de 224px que não cabe) e os filtros de
 * Pacientes (hoje uma linha de busca mais três seletores que estoura a
 * largura). Um componente só evita duas implementações de Esc, trava de
 * rolagem e clique-fora divergindo com o tempo.
 */
export function Drawer({ open, onClose, title, side = 'left', children }: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useOverlayLock(open, onClose)

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={[
          'absolute inset-y-0 flex w-[85%] max-w-xs flex-col bg-white shadow-xl',
          side === 'left' ? 'left-0' : 'right-0',
        ].join(' ')}
      >
        <div className="flex flex-shrink-0 items-center justify-between border-b border-gray-100 px-4 py-3">
          <h2 className="text-base font-semibold text-gray-800">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="-mr-2 flex h-11 w-11 items-center justify-center text-gray-400 transition-colors hover:text-gray-600 text-xl leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>
  )
}
