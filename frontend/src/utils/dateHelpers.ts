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


const SHORT_DAYS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
const SHORT_MONTHS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
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

/** Short month name from YYYY-MM-DD: "Mar", "Abr", etc. */
export function shortMonthName(dateStr: string): string {
  return SHORT_MONTHS[parseDate(dateStr).getMonth()]
}


/** "3 a 9 de Marco · 2026" or "3 de Marco a 9 de Abril · 2026" */
export function dateRangeLabel(first: string, last: string): string {
  const start = parseDate(first)
  const end = parseDate(last)
  const startDay = start.getDate()
  const endDay = end.getDate()
  const month = MONTHS[end.getMonth()]
  const year = end.getFullYear()

  if (first === last) {
    return `${startDay} de ${month} · ${year}`
  }
  if (start.getMonth() === end.getMonth()) {
    return `${startDay} a ${endDay} de ${month} · ${year}`
  }
  const startMonth = MONTHS[start.getMonth()]
  return `${startDay} de ${startMonth} a ${endDay} de ${month} · ${year}`
}


/** Convert "HH:MM:SS" or "HH:MM" to minutes since midnight */
export function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}
