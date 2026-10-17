import type { DiscountReason } from '@/types'

/**
 * O motivo do desconto em português, para o resumo. O backend manda só a
 * categoria — nunca o porquê de um desconto personalizado.
 */
export function discountLabel(reason: DiscountReason | null, areaCount: number): string | null {
  switch (reason) {
    case 'first_session':
      return 'Primeira sessão'
    case 'tier_2':
    case 'tier_3':
      return `${areaCount} áreas`
    case 'personalizado':
      return 'Desconto especial'
    default:
      return null
  }
}
