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
  email: z
    .string()
    .optional()
    .refine((v) => !v || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), 'E-mail inválido'),
}

/** `07903984519` → `079.039.845-19`. Só formata quando está completo. */
export function formataCpf(valor: string): string {
  const d = valor.replace(/\D/g, '').slice(0, 11)
  if (d.length !== 11) return d
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}
