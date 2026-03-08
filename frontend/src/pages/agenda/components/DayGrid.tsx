import { timeToMinutes, shortDayName, dayNumber } from '@/utils/dateHelpers'
import type { Appointment } from '@/types'

const FIRST_HOUR = 7
const LAST_HOUR = 20
const HOUR_HEIGHT = 48
const TOTAL_HOURS = LAST_HOUR - FIRST_HOUR
const HOURS = Array.from({ length: TOTAL_HOURS }, (_, i) => FIRST_HOUR + i)

interface DayGridProps {
  date: string
  appointments: Appointment[]
  onSlotClick: (date: string, time: string) => void
  onAppointmentClick: (appointment: Appointment, rect: DOMRect) => void
}

function appointmentStyle(a: Appointment): React.CSSProperties {
  const startMin = timeToMinutes(a.start_time)
  const endMin = timeToMinutes(a.end_time)
  const topMin = startMin - FIRST_HOUR * 60
  const durationMin = Math.max(endMin - startMin, 30)

  return {
    position: 'absolute',
    top: `${(topMin / 60) * HOUR_HEIGHT}px`,
    height: `${(durationMin / 60) * HOUR_HEIGHT - 2}px`,
    left: '2px',
    right: '2px',
  }
}

function AppointmentBlock({
  appointment,
  onClick,
}: {
  appointment: Appointment
  onClick: (a: Appointment, rect: DOMRect) => void
}) {
  const a = appointment
  const isCancelled = a.status === 'CANCELLED'
  const displayName = a.patient_name || a.full_name || 'Sem nome'
  const serviceLine = [a.service_name, a.areas].filter(Boolean).join(' · ')
  const timeSlot = `${a.start_time.slice(0, 5)}–${a.end_time.slice(0, 5)}`

  return (
    <button
      type="button"
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect()
        onClick(a, rect)
      }}
      style={appointmentStyle(a)}
      className={[
        'w-full text-left rounded-md px-3 py-1.5 border-l-3 overflow-hidden cursor-pointer transition-opacity hover:opacity-90',
        isCancelled
          ? 'bg-amber-50 border-l-amber-400 text-amber-800'
          : 'bg-brand-50 border-l-brand-500 text-brand-900',
      ].join(' ')}
    >
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-brand-600 whitespace-nowrap">{timeSlot}</span>
        <span className="text-sm font-semibold truncate">{displayName}</span>
      </div>
      {serviceLine && (
        <p className="text-xs truncate opacity-75 mt-0.5">{serviceLine}</p>
      )}
    </button>
  )
}

export function DayGrid({ date, appointments, onSlotClick, onAppointmentClick }: DayGridProps) {
  const dayAppts = appointments.filter((a) => a.appointment_date === date)

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="grid border-b border-gray-200" style={{ gridTemplateColumns: '60px 1fr' }}>
        <div className="border-r border-gray-100" />
        <div className="text-center py-1.5 bg-brand-500 text-white">
          <p className="text-[11px] font-medium leading-tight text-white/80">{shortDayName(date)}</p>
          <p className="text-base font-bold leading-tight">{dayNumber(date)}</p>
        </div>
      </div>

      {/* Body */}
      <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 170px)' }}>
        <div className="grid relative pt-2" style={{ gridTemplateColumns: '60px 1fr' }}>
          {/* Time labels */}
          <div className="relative" style={{ height: `${TOTAL_HOURS * HOUR_HEIGHT}px` }}>
            {HOURS.map((hour) => (
              <div
                key={hour}
                className="absolute right-0 left-0 flex items-start justify-end pr-2"
                style={{ top: `${(hour - FIRST_HOUR) * HOUR_HEIGHT}px`, height: `${HOUR_HEIGHT}px` }}
              >
                <span className="text-xs text-gray-400 -mt-2">
                  {String(hour).padStart(2, '0')}h
                </span>
              </div>
            ))}
          </div>

          {/* Day column */}
          <div className="relative border-r border-gray-100" style={{ height: `${TOTAL_HOURS * HOUR_HEIGHT}px` }}>
            {HOURS.map((hour) => (
              <button
                type="button"
                key={hour}
                className="absolute w-full border-t border-gray-100 hover:bg-brand-50/40 transition-colors cursor-pointer"
                style={{ top: `${(hour - FIRST_HOUR) * HOUR_HEIGHT}px`, height: `${HOUR_HEIGHT}px` }}
                onClick={() => onSlotClick(date, `${String(hour).padStart(2, '0')}:00`)}
              />
            ))}

            {dayAppts.map((a) => (
              <AppointmentBlock
                key={a.id}
                appointment={a}
                onClick={onAppointmentClick}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
