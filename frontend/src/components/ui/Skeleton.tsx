interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string
}

export function Skeleton({ className = '', ...props }: SkeletonProps) {
  return <div className={`animate-pulse rounded-md bg-gray-200 ${className}`} {...props} />
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-7 w-32 mb-1" />
      <Skeleton className="h-3 w-16" />
    </div>
  )
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}

const CHART_BAR_HEIGHTS = ['45%', '70%', '55%', '85%', '40%', '65%', '50%']

export function SkeletonChart() {
  return (
    <div className="flex items-end gap-2 h-40">
      {CHART_BAR_HEIGHTS.map((height, i) => (
        <Skeleton
          key={i}
          className="flex-1"
          style={{ height }}
        />
      ))}
    </div>
  )
}
