import { useCallback, useEffect, useRef, useState } from 'react'

interface ScrollAreaProps {
  /** Altura maxima em px. O container encolhe quando o conteudo e menor. */
  maxHeight: number
  children: React.ReactNode
  className?: string
}

/**
 * Container com altura maxima e rolagem interna.
 *
 * As mascaras de fade so aparecem quando ha conteudo cortado naquela direcao:
 * um fade permanente mentiria sobre o conteudo em listas curtas.
 */
export function ScrollArea({ maxHeight, children, className = '' }: ScrollAreaProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [fadeTop, setFadeTop] = useState(false)
  const [fadeBottom, setFadeBottom] = useState(false)

  const updateFades = useCallback(() => {
    const el = ref.current
    if (!el) return

    const { scrollTop, scrollHeight, clientHeight } = el
    // Tolerancia de 1px: alturas fracionarias nunca batem exato.
    setFadeTop(scrollTop > 1)
    setFadeBottom(scrollTop + clientHeight < scrollHeight - 1)
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return

    updateFades()

    // A lista muda de tamanho ao adicionar/excluir itens, sem evento de scroll.
    const observer = new ResizeObserver(updateFades)
    observer.observe(el)
    for (const child of Array.from(el.children)) observer.observe(child)

    return () => observer.disconnect()
  }, [updateFades, children])

  return (
    <div className={`relative ${className}`}>
      <div
        ref={ref}
        onScroll={updateFades}
        style={{ maxHeight, overscrollBehavior: 'contain' }}
        className="overflow-y-auto"
      >
        {children}
      </div>

      <div
        aria-hidden
        className={[
          'pointer-events-none absolute inset-x-0 top-0 h-6 transition-opacity duration-200',
          'bg-gradient-to-b from-white to-transparent',
          fadeTop ? 'opacity-100' : 'opacity-0',
        ].join(' ')}
      />
      <div
        aria-hidden
        className={[
          'pointer-events-none absolute inset-x-0 bottom-0 h-6 transition-opacity duration-200',
          'bg-gradient-to-t from-white to-transparent',
          fadeBottom ? 'opacity-100' : 'opacity-0',
        ].join(' ')}
      />
    </div>
  )
}
