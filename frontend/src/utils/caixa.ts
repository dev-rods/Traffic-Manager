import { toDateStr } from '@/utils/dateHelpers'

export type Faixa = 'hoje' | 'ontem' | '7dias' | 'mes'

export const FAIXAS: { value: Faixa; label: string }[] = [
  { value: 'hoje', label: 'Hoje' },
  { value: 'ontem', label: 'Ontem' },
  { value: '7dias', label: 'Últimos 7 dias' },
  { value: 'mes', label: 'Este mês' },
]

export function intervaloDa(faixa: Faixa, hoje: Date = new Date()): [string, string] {
  const dia = (delta: number) => {
    const d = new Date(hoje)
    d.setDate(d.getDate() + delta)
    return toDateStr(d)
  }
  if (faixa === 'ontem') return [dia(-1), dia(-1)]
  if (faixa === '7dias') return [dia(-6), dia(0)]
  if (faixa === 'mes') return [toDateStr(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), dia(0)]
  return [dia(0), dia(0)]
}
