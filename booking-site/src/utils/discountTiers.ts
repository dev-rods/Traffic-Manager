import type { DiscountTier } from '@/types'

function areas(n: number): string {
  return n === 1 ? '1 área' : `${n} áreas`
}

function tierRange(tier: DiscountTier): string {
  if (tier.maxAreas == null) return `${tier.minAreas} ou mais áreas`
  if (tier.maxAreas === tier.minAreas) return areas(tier.minAreas)
  return `${tier.minAreas} a ${tier.maxAreas} áreas`
}

/** "2 a 3 áreas: 10% off · 4 ou mais áreas: 20% off". `null` sem faixas. */
export function tiersSummary(tiers: DiscountTier[]): string | null {
  if (tiers.length === 0) return null
  return tiers.map((t) => `${tierRange(t)}: ${t.pct}% off`).join(' · ')
}

/**
 * Quanto falta para a próxima faixa, a partir da contagem de áreas que a
 * cotação devolve (depois dos combos, a mesma que o backend usa para cobrar).
 * `null` antes da primeira área e depois da última faixa.
 */
export function nextTierHint(tiers: DiscountTier[], areaCount: number): string | null {
  if (areaCount < 1) return null
  const next = tiers.find((t) => t.minAreas > areaCount)
  if (!next) return null
  const missing = next.minAreas - areaCount
  return `${missing === 1 ? 'Falta' : 'Faltam'} ${areas(missing)} para ${next.pct}% de desconto`
}
