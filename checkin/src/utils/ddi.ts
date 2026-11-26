import { formatPhone, isValidMobile, onlyDigits } from './format'

/**
 * Código do país no link de documentos (25/11/2026). Uma paciente da Essência
 * com número dos EUA não passou da etapa do celular: o campo só aceitava 11
 * dígitos brasileiros. Em vez de pedir que ela comece com "+", a pessoa
 * escolhe o país (Brasil por padrão) e a validação segue o país escolhido.
 *
 * Lista fixa de propósito (decisão do André): os países prováveis, mais
 * "Outro" com o código digitado à mão para não travar ninguém.
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

export function ddiValido(ddi: string): boolean {
  const d = onlyDigits(ddi)
  return d.length >= 1 && d.length <= 3
}

/** Brasil: celular com nono dígito. Fora: só dígitos, de 6 a 14. */
export function numeroValido(ddi: string, digits: string): boolean {
  const d = onlyDigits(digits)
  if (!ddiValido(ddi)) return false
  if (onlyDigits(ddi) === BRASIL) return isValidMobile(d)
  return d.length >= 6 && d.length <= 14
}

export function formataNumero(ddi: string, digits: string): string {
  const d = onlyDigits(digits)
  return onlyDigits(ddi) === BRASIL ? formatPhone(d) : d.slice(0, 14)
}

export function limiteDeDigitos(ddi: string): number {
  return onlyDigits(ddi) === BRASIL ? 11 : 14
}

/**
 * O que vai para a API. Brasil continua "55" + dígitos (o formato que o
 * backend sempre recebeu daqui). Fora, "+" + DDI + dígitos: o backend
 * normaliza número estrangeiro desde o PRD 033 e grava sem o "+".
 */
export function montaTelefone(ddi: string, digits: string): string {
  const codigo = onlyDigits(ddi)
  const d = onlyDigits(digits)
  return codigo === BRASIL ? `${BRASIL}${d}` : `+${codigo}${d}`
}

export function placeholderDoNumero(ddi: string): string {
  return onlyDigits(ddi) === BRASIL ? '(00) 00000-0000' : 'Só os números, sem o código do país'
}
