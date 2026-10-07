import { cx } from '@/utils/cx'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-9 w-9 border-[3px]',
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      className={cx(
        'inline-block animate-spin rounded-full border-current border-t-transparent',
        SIZES[size],
        className
      )}
    />
  )
}
