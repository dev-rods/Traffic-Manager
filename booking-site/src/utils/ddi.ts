import { formatPhoneInput, normalizePhoneDigits } from './format'

/**
 * Código do país nos campos de celular (PRD 067). Em vez de pedir que a
 * pessoa comece com "+" (PRD 033, ninguém descobria), ela escolhe o país,
 * Brasil por padrão, e a validação segue o país escolhido.
 *
 * A mesma lista e as mesmas funções existem em checkin/src/utils/ddi.ts e
 * frontend/src/utils/ddi.ts (apps separados, sem pacote comum). Mudar aqui é
 * mudar lá; os testes usam os mesmos vetores.
 */
export interface Pais {
  ddi: string
  nome: string
}

export const BRASIL = '55'
export const OUTRO = 'outro'

export const PAISES: Pais[] = [
  { ddi: '55', nome: 'Brasil' },
  { ddi: '1', nome: 'EUA / Canadá' },
  { ddi: '351', nome: 'Portugal' },
  { ddi: '54', nome: 'Argentina' },
  { ddi: '598', nome: 'Uruguai' },
  { ddi: '595', nome: 'Paraguai' },
  { ddi: '56', nome: 'Chile' },
  { ddi: '57', nome: 'Colômbia' },
  { ddi: '51', nome: 'Peru' },
  { ddi: '52', nome: 'México' },
  { ddi: '34', nome: 'Espanha' },
  { ddi: '39', nome: 'Itália' },
  { ddi: '33', nome: 'França' },
  { ddi: '49', nome: 'Alemanha' },
  { ddi: '44', nome: 'Reino Unido' },
  { ddi: '81', nome: 'Japão' },
]

const onlyDigits = normalizePhoneDigits

export function ddiValido(ddi: string): boolean {
  const d = onlyDigits(ddi)
  return d.length >= 1 && d.length <= 3
}

/** Brasil: DDD + número, 10 ou 11 dígitos (regra que o site já usava). Fora: 6 a 14. */
export function numeroValido(ddi: string, digits: string): boolean {
  const d = onlyDigits(digits)
  if (!ddiValido(ddi)) return false
  if (onlyDigits(ddi) === BRASIL) return d.length === 10 || d.length === 11
  return d.length >= 6 && d.length <= 14
}

export function formataNumero(ddi: string, digits: string): string {
  const d = onlyDigits(digits)
  return onlyDigits(ddi) === BRASIL ? formatPhoneInput(d) : d.slice(0, 14)
}

export function limiteDeDigitos(ddi: string): number {
  return onlyDigits(ddi) === BRASIL ? 11 : 14
}

export function placeholderDoNumero(ddi: string): string {
  return onlyDigits(ddi) === BRASIL ? 'Digite seu celular' : 'Só os números, sem o código do país'
}

/**
 * A string que o resto do site já entende (`toApiPhone`, `isValidPhone`,
 * sessão verificada): Brasil formatado, fora `+DDI` + número. Número de fora
 * incompleto vira vazio, para nenhum botão habilitar com ele.
 */
export function valorDoSite(ddi: string, digits: string): string {
  const codigo = onlyDigits(ddi)
  const d = onlyDigits(digits)
  if (codigo === BRASIL) return formatPhoneInput(d)
  return numeroValido(codigo, d) ? `+${codigo}${d}` : ''
}

/**
 * O país de um número (PRD 067), para reabrir o campo como estava: `55` +
 * DDD + número é Brasil; DDI na frente, o prefixo mais longo da lista. Sem
 * casamento, "Outro país" com o número inteiro, para a pessoa completar o
 * código.
 */
export function paisDoNumero(gravado: string | null | undefined): { pais: string; ddiLivre: string; digits: string } {
  const bruto = (gravado ?? '').trim()
  const d = onlyDigits(bruto)
  if (!d) return { pais: BRASIL, ddiLivre: '', digits: '' }
  if (d.startsWith(BRASIL) && (d.length === 12 || d.length === 13)) {
    return { pais: BRASIL, ddiLivre: '', digits: d.slice(2) }
  }
  // Sem DDI: celular brasileiro (11 dígitos, 9 depois do DDD) ou fixo (10).
  // Um 11 dígitos sem o 9 é estrangeiro gravado sem +, como 1 202 555 0147.
  if (!bruto.startsWith('+') && (d.length === 10 || (d.length === 11 && d[2] === '9'))) {
    return { pais: BRASIL, ddiLivre: '', digits: d }
  }
  const candidatos = PAISES.filter((p) => p.ddi !== BRASIL).sort((a, b) => b.ddi.length - a.ddi.length)
  for (const p of candidatos) {
    const resto = d.slice(p.ddi.length)
    if (d.startsWith(p.ddi) && resto.length >= 6 && resto.length <= 14) {
      return { pais: p.ddi, ddiLivre: '', digits: resto }
    }
  }
  return { pais: OUTRO, ddiLivre: '', digits: d.slice(0, 14) }
}
