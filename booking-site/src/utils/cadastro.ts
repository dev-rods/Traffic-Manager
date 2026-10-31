import type { CampoDoCadastro } from '@/types'

/**
 * Cadastro do paciente pedido pelo site (PRD 032): CPF, nascimento e e-mail.
 * A validação aqui é para a pessoa saber na hora que digitou errado; o
 * servidor confere de novo (`utils/cadastro.py`) e decide.
 */

export function onlyDigits(value: string): string {
  return value.replace(/\D/g, '')
}

/** `000.000.000-00` enquanto digita. Copiado do check-in. */
export function formatCpf(value: string): string {
  const d = onlyDigits(value).slice(0, 11)
  if (d.length <= 3) return d
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}

/** Dígitos verificadores. Copiado do check-in. */
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

/** `DD/MM/AAAA` enquanto digita. */
export function formatDateInput(value: string): string {
  const d = onlyDigits(value).slice(0, 8)
  if (d.length <= 2) return d
  if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`
  return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`
}

/** `31/10/1990` -> `1990-10-31`; null quando não é uma data real. */
export function brDateToIso(value: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim())
  if (!m) return null
  const [, dd, mm, yyyy] = m
  const day = Number(dd)
  const month = Number(mm)
  const year = Number(yyyy)
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null
  return `${yyyy}-${mm}-${dd}`
}

/** Data real, no passado (ou hoje), de 1900 para cá. */
export function isValidBirthDate(value: string): boolean {
  const iso = brDateToIso(value)
  if (!iso) return false
  const year = Number(iso.slice(0, 4))
  if (year < 1900) return false
  const today = new Date()
  const hoje = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  return iso <= hoje
}

/** Mesma regra do backend (`utils/cadastro.normaliza_email`). */
export function isValidEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
}

export const ROTULO_DO_CAMPO: Record<CampoDoCadastro, string> = {
  cpf: 'CPF',
  birth_date: 'data de nascimento',
  email: 'e-mail',
}

/** "CPF, data de nascimento e e-mail" para a mensagem de erro. */
export function listaDeCampos(campos: CampoDoCadastro[]): string {
  const nomes = campos.map((c) => ROTULO_DO_CAMPO[c])
  if (nomes.length <= 1) return nomes.join('')
  return `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}`
}
