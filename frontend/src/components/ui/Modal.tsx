import { useRef } from 'react'
import { useOverlayLock } from '@/hooks/useOverlayLock'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  width?: 'sm' | 'md' | 'lg'
}

const WIDTH_CLASSES = {
  sm: 'md:max-w-sm',
  md: 'md:max-w-md',
  lg: 'md:max-w-lg',
}

/**
 * A janela compartilhada por 13 telas - inclusive o registro de sessão, a
 * criação e a edição de agendamento.
 *
 * **Em celular ela ocupa a tela inteira.** Um retângulo centralizado de 448px
 * com margem de 16px não sobra quase nada numa tela de 375px, e o pouco que
 * sobra some quando o teclado virtual abre: o botão de salvar sai da área
 * visível e o formulário vira um beco. Tela cheia devolve a altura toda e
 * mantém cabeçalho e rodapé nos seus lugares.
 *
 * Acima de `md` nada mudou: mesma largura, mesmo canto arredondado, mesmo
 * fundo escurecido.
 */
export function Modal({ open, onClose, title, children, width = 'md' }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useOverlayLock(open, onClose)

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex md:items-center md:justify-center bg-black/40 backdrop-blur-sm md:p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div
        className={[
          // Em celular: a tela toda. `h-full` em vez de `max-h`, para o
          // conteúdo poder empurrar o rodapé para baixo em vez de encolher.
          'w-full h-full flex flex-col bg-white shadow-xl',
          // De `md` para cima, a janela de sempre.
          'md:h-auto md:max-h-[calc(100vh-2rem)] md:rounded-xl',
          WIDTH_CLASSES[width],
        ].join(' ')}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 flex-shrink-0">
          <h2 className="text-base font-semibold text-gray-800">{title}</h2>
          {/* 44px de alvo: o `×` de 16px era mirável com o mouse e não com o
              dedo. `-mr-2` devolve o alinhamento visual que o padding rouba. */}
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="-mr-2 flex h-11 w-11 items-center justify-center text-gray-400 hover:text-gray-600 transition-colors text-xl leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  )
}
