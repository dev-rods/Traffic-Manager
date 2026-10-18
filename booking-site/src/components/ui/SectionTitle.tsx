import type { ReactNode } from 'react'

/**
 * Título de etapa em frase normal, negrito e grafite, como na referência
 * ("Selecione o profissional"). Os títulos em caixa alta, marrons e espaçados
 * pareciam rótulo de formulário e não guiavam (PRD 025, V3).
 */
export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 font-display text-lg font-semibold text-ink-900">{children}</h2>
}
