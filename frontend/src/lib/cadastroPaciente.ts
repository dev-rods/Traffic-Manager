import { z } from 'zod'

/**
 * CPF e data de nascimento no schema, ambos opcionais.
 *
 * Opcionais porque o cadastro completo raramente existe no primeiro contato: a
 * pessoa marca pelo WhatsApp e a recepção completa depois. Exigir aqui travaria
 * o cadastro por um dado que chega no dia da sessão.
 *
 * O CPF é validado só por tamanho. Dígito verificador fica de fora de propósito
 * - recusar um CPF ditado errado no WhatsApp travaria o agendamento por algo
 * que a recepção corrige em dois segundos. `src/utils/cadastro.py` no backend
 * toma a mesma decisão, e as duas precisam concordar.
 */
export const cadastroSchema = {
  cpf: z
    .string()
    .optional()
    .refine((v) => !v || v.replace(/\D/g, '').length === 11, 'CPF deve ter 11 dígitos'),
  birth_date: z.string().optional(),
  /**
   * Desconto fixo da paciente. Texto no formulario porque vazio precisa
   * sobreviver ate o envio: e assim que a clinica desfaz um combinado. Virar
   * numero cedo transformaria o vazio em 0, que significa outra coisa.
   */
  custom_discount_pct: z
    .string()
    .optional()
    .refine((v) => {
      if (!v || !v.trim()) return true
      const n = Number(v)
      return Number.isInteger(n) && n >= 0 && n <= 100
    }, 'Informe um numero inteiro de 0 a 100'),
  email: z
    .string()
    .optional()
    .refine((v) => !v || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), 'E-mail inválido'),
}

/**
 * O que vai a API no campo de desconto: `null` quando a clinica apagou o campo,
 * inteiro quando digitou. Undefined nunca - a diferenca entre "nao mexi" e
 * "apaguei" nao existe neste formulario, e mandar undefined deixaria o
 * combinado antigo intacto quando a intencao era remove-lo.
 */
export function descontoParaApi(valor: string | undefined): number | null {
  if (!valor || !valor.trim()) return null
  return Number(valor)
}

/** `07903984519` → `079.039.845-19`. Só formata quando está completo. */
export function formataCpf(valor: string): string {
  const d = valor.replace(/\D/g, '').slice(0, 11)
  if (d.length !== 11) return d
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}
