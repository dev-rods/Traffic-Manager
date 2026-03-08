interface KpiCardProps {
  label: string
  value: string
  valueColor?: string
  subtext: string
  subtextColor?: string
}

export function KpiCard({ label, value, valueColor = 'text-gray-800', subtext, subtextColor = 'text-emerald-500' }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-gray-400 font-medium">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${valueColor}`}>{value}</p>
      <p className={`text-xs mt-1 ${subtextColor}`}>{subtext}</p>
    </div>
  )
}
