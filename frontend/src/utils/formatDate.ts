/**
 * Formats an ISO date string to a human-readable date in pt-BR.
 * @example formatDate("2026-03-08T09:00:00Z") → "8 Mar 2026"
 */
export function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'America/Sao_Paulo',
  })
    .format(new Date(isoString))
    .replace('.', '') // remove trailing dot from month abbreviation
}

/**
 * Formats an ISO date string to time only.
 * @example formatTime("2026-03-08T12:00:00Z") → "09:00"
 */
export function formatTime(isoString: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Sao_Paulo',
  }).format(new Date(isoString))
}

/**
 * Formats a plain calendar date (YYYY-MM-DD, no time component) in pt-BR.
 *
 * Parses at noon on purpose: `new Date("2026-03-08")` is read as UTC midnight,
 * which lands on the previous day in America/Sao_Paulo.
 *
 * @example formatCalendarDate("2026-03-08") → "08/03/2026"
 */
export function formatCalendarDate(dateOnly: string): string {
  return new Date(`${dateOnly}T12:00:00`).toLocaleDateString('pt-BR')
}

/**
 * Formats a `HH:MM:SS` (or `HH:MM`) clock value to `HH:MM`.
 * @example formatClock("09:00:00") → "09:00"
 */
export function formatClock(clock: string): string {
  return clock.slice(0, 5)
}

/**
 * Returns a short weekday + date label.
 * @example formatShortDate("2026-03-08T09:00:00Z") → "Sáb, 8 Mar"
 */
export function formatShortDate(isoString: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'America/Sao_Paulo',
  })
    .format(new Date(isoString))
    .replace(/\./g, '')
}
