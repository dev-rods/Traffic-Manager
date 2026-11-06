import { cx } from '@/utils/cx'

interface SimNaoProps {
  label: string
  value: boolean | null
  onChange: (value: boolean) => void
  error?: string | null
}

/**
 * Par "Sim"/"Não" da ficha de anamnese (PRD 038). Sem opção padrão: cada
 * pergunta exige um toque, para "Não" por pressa não virar resposta. Alvos
 * de 64 px, como o resto do quiosque.
 */
export function SimNao({ label, value, onChange, error }: SimNaoProps) {
  return (
    <div className="flex flex-col gap-2" role="radiogroup" aria-label={label}>
      <span className="text-lg leading-snug text-ink-800">{label}</span>
      <div className="grid grid-cols-2 gap-3">
        {[
          { v: true, text: 'Sim' },
          { v: false, text: 'Não' },
        ].map(({ v, text }) => (
          <button
            key={text}
            type="button"
            role="radio"
            aria-checked={value === v}
            onClick={() => onChange(v)}
            className={cx(
              'min-h-16 rounded-2xl border-2 px-4 font-display text-xl font-bold transition-colors duration-150',
              value === v
                ? 'border-success-500 bg-success-100 text-success-600'
                : 'border-ink-200 bg-surface text-ink-800 active:bg-accent-50'
            )}
          >
            {text}
          </button>
        ))}
      </div>
      {error ? (
        <span role="alert" className="text-base text-danger-500">
          {error}
        </span>
      ) : null}
    </div>
  )
}
