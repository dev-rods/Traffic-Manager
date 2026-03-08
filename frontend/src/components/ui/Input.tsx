import { forwardRef } from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div>
        {label && (
          <label className="text-xs font-medium text-gray-500 block mb-1">{label}</label>
        )}
        <input
          ref={ref}
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
