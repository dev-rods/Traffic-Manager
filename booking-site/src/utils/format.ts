/** Preço que vale mostrar: zero ou ausente é "a consultar", nunca "R$ 0,00". */
export function hasPrice(cents: number | null | undefined): cents is number {
  return cents != null && cents > 0
}

export function formatCurrencyBRL(cents: number | null | undefined): string {
  if (cents == null) return ''
  return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function formatDateBR(isoDate: string): string {
  const [y, m, d] = isoDate.split('-')
  return `${d}/${m}/${y}`
}

const WEEKDAY_LONG = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']

export function formatDateLong(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return `${WEEKDAY_LONG[date.getDay()]}, ${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`
}

export function normalizePhoneDigits(value: string): string {
  return value.replace(/\D/g, '')
}

export function formatPhoneInput(value: string): string {
  const digits = normalizePhoneDigits(value).slice(0, 11)
  if (digits.length <= 2) return digits
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
}

export function isValidBrPhone(value: string): boolean {
  const digits = normalizePhoneDigits(value)
  return digits.length === 10 || digits.length === 11
}

export function toApiPhone(value: string): string {
  const digits = normalizePhoneDigits(value)
  return digits.startsWith('55') ? digits : `55${digits}`
}

/** Número no formato da API (`5511999990000`) para leitura: `(11) 99999-0000`. */
export function formatPhoneDisplay(apiPhone: string): string {
  const digits = normalizePhoneDigits(apiPhone)
  const local = digits.length > 11 && digits.startsWith('55') ? digits.slice(2) : digits
  if (local.length === 10) return `(${local.slice(0, 2)}) ${local.slice(2, 6)}-${local.slice(6)}`
  return formatPhoneInput(local)
}
