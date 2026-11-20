import { forwardRef, useId } from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', id, ...props }, ref) => {
    // Rótulo ligado ao campo: clicar no texto foca o input e o leitor de tela
    // anuncia o nome. Sem isto o `label` era só visual.
    const gerado = useId()
    const inputId = id ?? (label ? gerado : undefined)
    return (
      <div>
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-gray-500 block mb-1">{label}</label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={[
            'w-full border rounded-lg px-3 py-2.5 text-sm bg-white transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-brand-500',
            error ? 'border-red-400' : 'border-gray-200',
            className,
          ].join(' ')}
          {...props}
        />
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'
