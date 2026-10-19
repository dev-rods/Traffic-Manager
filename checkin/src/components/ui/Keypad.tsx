import { cx } from '@/utils/cx'

interface KeypadProps {
  value: string
  maxLength: number
  onChange: (digits: string) => void
  disabled?: boolean
}

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'clear', '0', 'back'] as const

/**
 * Teclado numérico na própria tela. O teclado do iPad cobre metade dela,
 * muda de layout entre campos e traz letras que aqui não servem; no totem, os
 * números ficam sempre no mesmo lugar, grandes.
 */
export function Keypad({ value, maxLength, onChange, disabled }: KeypadProps) {
  function press(key: (typeof KEYS)[number]) {
    if (key === 'clear') onChange('')
    else if (key === 'back') onChange(value.slice(0, -1))
    else if (value.length < maxLength) onChange(value + key)
  }

  return (
    <div className="mx-auto grid w-full max-w-sm grid-cols-3 gap-3">
      {KEYS.map((key) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => press(key)}
          aria-label={key === 'back' ? 'Apagar' : key === 'clear' ? 'Limpar' : key}
          className={cx(
            'h-[4.5rem] select-none rounded-2xl font-display transition-colors duration-100 disabled:opacity-40',
            key === 'clear' || key === 'back'
              ? 'bg-transparent text-base font-semibold text-ink-600 active:bg-ink-100'
              : 'bg-surface text-3xl font-semibold text-ink-900 shadow-card active:bg-accent-100'
          )}
        >
          {key === 'back' ? '⌫' : key === 'clear' ? 'Limpar' : key}
        </button>
      ))}
    </div>
  )
}
