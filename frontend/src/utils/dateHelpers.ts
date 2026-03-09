/** Parse YYYY-MM-DD without timezone shift */
export function parseDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Format Date to YYYY-MM-DD */
export function toDateStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** Today as YYYY-MM-DD */
export function todayStr(): string {
  return toDateStr(new Date())
}

/** Add days to a YYYY-MM-DD string */
export function addDays(dateStr: string, days: number): string {
  const d = parseDate(dateStr)
  d.setDate(d.getDate() + days)
  return toDateStr(d)
}

/** Get Monday of the week containing dateStr */
export function getWeekStart(dateStr: string): string {
  const d = parseDate(dateStr)
  const day = d.getDay() // 0=Sun
  const diff = day === 0 ? -6 : 1 - day // Monday
  d.setDate(d.getDate() + diff)
  return toDateStr(d)
}

/** Get Sunday of the week containing dateStr */
export function getWeekEnd(dateStr: string): string {
  return addDays(getWeekStart(dateStr), 6)
}

/** Get all 7 days of the week as YYYY-MM-DD strings */
export function getWeekDays(weekStart: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

const SHORT_DAYS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
const MONTHS = [
  'Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

/** "Seg" / "Ter" etc */
export function shortDayName(dateStr: string): string {
  return SHORT_DAYS[parseDate(dateStr).getDay()]
}

/** Day number from YYYY-MM-DD */
export function dayNumber(dateStr: string): number {
  return parseDate(dateStr).getDate()
}

/** "Semana de 3 a 9 de Marco · 2026" */
export function weekRangeLabel(weekStart: string): string {
  const start = parseDate(weekStart)
  const end = parseDate(addDays(weekStart, 6))
  const startDay = start.getDate()
  const endDay = end.getDate()
  const month = MONTHS[end.getMonth()]
  const year = end.getFullYear()

  if (start.getMonth() === end.getMonth()) {
    return `Semana de ${startDay} a ${endDay} de ${month} · ${year}`
  }
  const startMonth = MONTHS[start.getMonth()]
  return `Semana de ${startDay} de ${startMonth} a ${endDay} de ${month} · ${year}`
}

/** Convert "HH:MM:SS" or "HH:MM" to minutes since midnight */
export function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}
