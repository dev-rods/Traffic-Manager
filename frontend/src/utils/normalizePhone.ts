/**
 * Normaliza telefone brasileiro para formato canônico: 55DDDNNNNNNNNN (apenas dígitos).
 * Mesma lógica de scheduler/src/utils/phone.py → normalize_phone().
 */
export function normalizePhone(phone: string): string {
  let digits = phone.replace(/\D/g, '')

  // Remove leading 0 (ex: 011999990000)
  if (digits.startsWith('0')) {
    digits = digits.slice(1)
  }

  // Add country code if missing
  if (!digits.startsWith('55')) {
    digits = '55' + digits
  }

  return digits
}
