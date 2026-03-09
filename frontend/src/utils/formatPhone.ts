import { normalizePhone } from './normalizePhone'

/**
 * Formata telefone para exibição: (DD) NNNNN-NNNN
 * Mesma lógica de scheduler/src/utils/phone.py → format_phone_display().
 */
export function formatPhone(phone: string): string {
  let digits = normalizePhone(phone)

  // Remove country code (55)
  if (digits.startsWith('55')) {
    digits = digits.slice(2)
  }

  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  }

  return phone
}
