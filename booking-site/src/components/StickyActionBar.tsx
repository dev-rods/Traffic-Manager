import type { ReactNode } from 'react'

interface StickyActionBarProps {
  // Resumo à esquerda da ação ("2 áreas · R$ 225,00").
  summary: ReactNode
  children: ReactNode
}

/**
 * A ação da etapa presa no rodapé da tela. A lista de áreas passa de 30
 * itens, e o "Continuar" no fim dela não era visto: a pessoa marcava as
 * áreas e não sabia como seguir. Ocupa a largura da coluna e respeita a
 * área segura do celular.
 */
export function StickyActionBar({ summary, children }: StickyActionBarProps) {
  return (
    <div className="sticky bottom-0 z-10 -mx-5 mt-6 border-t border-ink-200 bg-ink-50 px-5 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_16px_rgb(30_30_40/0.06)] sm:-mx-10 sm:px-10">
      <div
        className="mb-2 flex items-center justify-between gap-3 text-sm text-ink-700"
        aria-live="polite"
      >
        {summary}
      </div>
      <div className="flex flex-col">{children}</div>
    </div>
  )
}
