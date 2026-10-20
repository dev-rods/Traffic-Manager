export function onlyDigits(value: string): string {
  return value.replace(/\D/g, '')
}

export function formatCurrencyBRL(cents: number | null | undefined): string {
  if (cents == null) return ''
  return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

const WEEKDAY_LONG = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
const MONTH_LONG = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

/** `2026-10-20` → `terça, 20 de outubro`. */
export function formatDateLong(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return `${WEEKDAY_LONG[date.getDay()]}, ${d} de ${MONTH_LONG[m - 1]}`
}

/** Só a primeira letra: "Terça, 20 de outubro", não "Terça, 20 De Outubro". */
export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Hoje no relógio do iPad, que fica na clínica. */
export function isToday(isoDate: string, now: Date = new Date()): boolean {
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  return now.getFullYear() === y && now.getMonth() === m - 1 && now.getDate() === d
}

export function formatPhone(digits: string): string {
  const d = onlyDigits(digits).slice(0, 11)
  if (d.length <= 2) return d
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}

export function isValidMobile(digits: string): boolean {
  const d = onlyDigits(digits)
  return d.length === 11 && d[2] === '9'
}

export function toApiPhone(digits: string): string {
  const d = onlyDigits(digits)
  return d.startsWith('55') ? d : `55${d}`
}

export function formatCpf(digits: string): string {
  const d = onlyDigits(digits).slice(0, 11)
  if (d.length <= 3) return d
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}

/**
 * Dígitos verificadores. O backend confere de novo; aqui é para a pessoa
 * saber na hora que digitou errado, sem esperar o servidor.
 */
export function isValidCpf(value: string): boolean {
  const d = onlyDigits(value)
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false
  for (const size of [9, 10]) {
    let sum = 0
    for (let i = 0; i < size; i++) sum += Number(d[i]) * (size + 1 - i)
    if (((sum * 10) % 11) % 10 !== Number(d[size])) return false
  }
  return true
}
