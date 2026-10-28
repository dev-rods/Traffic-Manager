import { cx } from '@/utils/cx'

const SIZES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-12 w-12 border-4',
}

export function Spinner({
  size = 'md',
  className,
}: {
  size?: keyof typeof SIZES
  className?: string
}) {
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
