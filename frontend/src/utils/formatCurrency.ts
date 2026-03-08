/**
 * Formats an amount in cents to Brazilian Real (BRL) currency string.
 * @example formatCurrency(18000) → "R$ 180,00"
 */
export function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(cents / 100)
}

/**
 * Returns the discount amount in cents.
 */
export function discountAmount(originalCents: number, discountPct: number): number {
  return Math.round(originalCents * (discountPct / 100))
}

/**
 * Returns the final price after applying discount.
 */
export function applyDiscount(originalCents: number, discountPct: number): number {
  return originalCents - discountAmount(originalCents, discountPct)
}
