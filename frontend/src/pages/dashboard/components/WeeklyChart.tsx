import { Card, CardHeader } from '@/components/ui/Card'
import type { DailyCount } from '@/services/reports.service'

interface WeeklyChartProps {
  dailyCounts: DailyCount[]
}

const WEEKDAY_SHORT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']

function getWeekday(dateStr: string): string {
  const date = new Date(dateStr + 'T12:00:00') // noon to avoid timezone shift
  return WEEKDAY_SHORT[date.getDay()]
}

function isToday(dateStr: string): boolean {
  const today = new Date()
  const d = new Date(dateStr + 'T12:00:00')
  return (
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  )
}

export function WeeklyChart({ dailyCounts }: WeeklyChartProps) {
  const max = Math.max(...dailyCounts.map((d) => d.count), 1)
  const total = dailyCounts.reduce((sum, d) => sum + d.count, 0)

  return (
    <Card>
      <CardHeader title="Semana" subtitle={`${total} agendamentos`} />

      <div className="flex items-end gap-2 h-40">
        {dailyCounts.map((day) => {
          const heightPct = (day.count / max) * 100
          const today = isToday(day.date)

          return (
            <div key={day.date} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-xs font-medium text-gray-600">{day.count}</span>
              <div className="w-full relative" style={{ height: '120px' }}>
                <div
                  className={`absolute bottom-0 w-full rounded-t-md transition-all ${
                    today ? 'bg-brand-500' : 'bg-brand-200'
                  }`}
                  style={{ height: `${Math.max(heightPct, 4)}%` }}
                />
              </div>
              <span
                className={`text-xs ${
                  today ? 'font-bold text-brand-700' : 'text-gray-400'
                }`}
              >
                {getWeekday(day.date)}
              </span>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
