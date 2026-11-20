import {
  formataPct,
  formataReais,
  rotuloDaRazao,
  validaDesconto,
  type DescontoEscolhido,
  type ModoDeDesconto,
  type TipoDeDesconto,
} from '@/lib/desconto'
import type { Cotacao } from '@/types'

interface DescontoFieldProps {
  valor: DescontoEscolhido
  onChange: (d: DescontoEscolhido) => void
  /** Teto do desconto em reais. Sem ele, o teto só é conferido pelo servidor. */
  subtotalCents?: number
  disabled?: boolean
  /** O que a política decide (PRD 053). `undefined` = ainda sem áreas ou paciente. */
  cotacao?: Cotacao | null
  cotando?: boolean
  erroDaCotacao?: boolean
}

const MODOS: ReadonlyArray<{ key: ModoDeDesconto; label: string }> = [
  { key: 'policy', label: 'Política da clínica' },
  { key: 'none', label: 'Sem desconto' },
  { key: 'partnership', label: 'Parceria (100%)' },
  { key: 'custom', label: 'Personalizado' },
]

const TIPOS: ReadonlyArray<{ key: TipoDeDesconto; label: string }> = [
  { key: 'pct', label: '%' },
  { key: 'cents', label: 'R$' },
]

/** A linha abaixo de "Política da clínica": o que o backend vai gravar. */
function textoDaCotacao(cotacao: Cotacao | null | undefined, cotando: boolean, erro: boolean): string {
  if (erro) return 'Não foi possível consultar a política. O desconto é aplicado ao salvar.'
  if (cotando) return 'Consultando a política…'
  if (cotacao === undefined) return 'Escolha a paciente e as áreas para ver o desconto.'
  if (!cotacao || !cotacao.discountPct) return 'Sem desconto pela política para esta paciente e estas áreas.'
  const economia =
    cotacao.originalPriceCents != null && cotacao.finalPriceCents != null
      ? ` (-${formataReais(cotacao.originalPriceCents - cotacao.finalPriceCents)})`
      : ''
  return `${rotuloDaRazao(cotacao.discountReason)}: ${formataPct(cotacao.discountPct)}%${economia}`
}

/**
 * O desconto de um agendamento, nas duas formas (PRD 050).
 *
 * É o mesmo campo nos dois modais da agenda, de propósito: a seção era
 * duplicada e a regra nova nasceria em dois lugares. Em "Personalizado", a
 * pessoa escolhe entre percentual e reais e digita num campo só, com vírgula
 * ou ponto. O erro só aparece quando há texto e ele é inválido; campo em
 * branco é problema do submit, não de quem está digitando.
 */
export function DescontoField({
  valor,
  onChange,
  subtotalCents,
  disabled = false,
  cotacao,
  cotando = false,
  erroDaCotacao = false,
}: DescontoFieldProps) {
  const erro = valor.texto.trim() ? validaDesconto(valor, subtotalCents) : null

  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1.5">Desconto</label>
      <div className="flex gap-2">
        {MODOS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            disabled={disabled}
            aria-pressed={valor.modo === key}
            onClick={() => onChange({ ...valor, modo: key })}
            className={[
              'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border disabled:opacity-50',
              valor.modo === key
                ? key === 'partnership'
                  ? 'bg-amber-50 border-amber-300 text-amber-700'
                  : key === 'custom'
                    ? 'bg-brand-50 border-brand-300 text-brand-700'
                    : key === 'policy'
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'bg-gray-900 border-gray-900 text-white'
                : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {valor.modo === 'policy' && (
        <p className={`mt-2 text-xs ${erroDaCotacao ? 'text-amber-600' : 'text-gray-500'}`} data-testid="cotacao">
          {textoDaCotacao(cotacao, cotando, erroDaCotacao)}
        </p>
      )}

      {valor.modo === 'custom' && (
        <>
          <div className="mt-2 flex items-center gap-2">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden" role="group" aria-label="Tipo de desconto">
              {TIPOS.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  disabled={disabled}
                  aria-pressed={valor.tipo === key}
                  // Trocar o tipo limpa o texto: "20" em % e "20" em R$ são
                  // descontos diferentes, e carregar o número induziria ao erro.
                  onClick={() => valor.tipo !== key && onChange({ ...valor, tipo: key, texto: '' })}
                  className={[
                    'px-3 py-2 text-xs font-semibold transition-colors duration-150 disabled:opacity-50',
                    valor.tipo === key
                      ? 'bg-brand-50 text-brand-700'
                      : 'bg-white text-gray-400 hover:text-gray-600',
                  ].join(' ')}
                >
                  {label}
                </button>
              ))}
            </div>
            <input
              type="text"
              inputMode="decimal"
              aria-label={valor.tipo === 'cents' ? 'Desconto em reais' : 'Desconto em porcento'}
              placeholder={valor.tipo === 'cents' ? 'Ex: 20,00' : 'Ex: 12,5'}
              value={valor.texto}
              disabled={disabled}
              onChange={(e) => onChange({ ...valor, texto: e.target.value })}
              className="w-28 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
            <span className="text-sm text-gray-500">de desconto</span>
          </div>
          {erro && <p className="mt-1.5 text-xs text-red-500">{erro}</p>}
        </>
      )}
    </div>
  )
}
