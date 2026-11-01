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

/**
 * Número de fora do Brasil começa com `+` e vai com o código do país; a
 * máscara nacional só vale para quem não digita o `+`. Uma paciente da Holanda
 * não conseguia agendar com o próprio celular (PRD 033).
 */
export function isInternationalPhone(value: string): boolean {
  return value.trim().startsWith('+') && !normalizePhoneDigits(value).startsWith('55')
}

export function formatPhoneInput(value: string): string {
  if (isInternationalPhone(value)) return `+${normalizePhoneDigits(value).slice(0, 15)}`
  const digits = normalizePhoneDigits(value).slice(0, 11)
  if (digits.length <= 2) return digits
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
}

export function isValidBrPhone(value: string): boolean {
  const digits = normalizePhoneDigits(value)
  return digits.length === 10 || digits.length === 11
}

/** Brasileiro com DDD, ou internacional com `+` e 8 a 15 dígitos (E.164). */
export function isValidPhone(value: string): boolean {
  if (isInternationalPhone(value)) {
    const digits = normalizePhoneDigits(value)
    return digits.length >= 8 && digits.length <= 15
  }
  return isValidBrPhone(value)
}

/** O que vai para a API: com `+` quando é internacional, para o servidor não
 * tratar o número como brasileiro. */
export function toApiPhone(value: string): string {
  const digits = normalizePhoneDigits(value)
  if (isInternationalPhone(value)) return `+${digits}`
  return digits.startsWith('55') ? digits : `55${digits}`
}

/** Número no formato da API (`5511999990000`) para leitura: `(11) 99999-0000`.
 * Internacional sai como `+31617223202`. */
export function formatPhoneDisplay(apiPhone: string): string {
  const digits = normalizePhoneDigits(apiPhone)
  if (isInternationalPhone(apiPhone)) return `+${digits}`
  const local = digits.length > 11 && digits.startsWith('55') ? digits.slice(2) : digits
  if (local.length === 10) return `(${local.slice(0, 2)}) ${local.slice(2, 6)}-${local.slice(6)}`
  return formatPhoneInput(local)
}
