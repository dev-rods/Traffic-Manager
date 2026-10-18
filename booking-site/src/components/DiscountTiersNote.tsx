import type { DiscountTier } from '@/types'
import { nextTierHint, tiersSummary } from '@/utils/discountTiers'

interface DiscountTiersNoteProps {
  tiers: DiscountTier[]
  // Contagem da cotação (depois dos combos); `undefined` enquanto não há.
  areaCount: number | undefined
}

/**
 * O desconto progressivo anunciado antes da escolha: com o preço à vista,
 * quem marca várias áreas precisa saber que o desconto cresce, e quanto
 * falta para a próxima faixa. O valor cobrado continua sendo o de /quote.
 */
export function DiscountTiersNote({ tiers, areaCount }: DiscountTiersNoteProps) {
  const summary = tiersSummary(tiers)
  if (!summary) return null
  const hint = areaCount === undefined ? null : nextTierHint(tiers, areaCount)

  return (
    <div className="mb-4 rounded-2xl bg-accent-50 px-4 py-3 text-sm">
      <p className="text-ink-700">
        <span className="font-semibold text-ink-900">Desconto progressivo</span> · {summary}
      </p>
      {hint ? (
        <p className="mt-1 font-medium text-accent-600" aria-live="polite">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
