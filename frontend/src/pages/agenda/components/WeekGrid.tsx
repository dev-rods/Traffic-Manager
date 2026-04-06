import { shortDayName, dayNumber, shortMonthName, todayStr, timeToMinutes } from '@/utils/dateHelpers'
import type { Appointment } from '@/types'

const FIRST_HOUR = 7
const LAST_HOUR = 22
const SLOT_MINUTES = 15
const HOUR_HEIGHT = 48 // px per hour
const SLOT_HEIGHT = HOUR_HEIGHT / (60 / SLOT_MINUTES) // px per 15-min slot
const TOTAL_HOURS = LAST_HOUR - FIRST_HOUR
const HOURS = Array.from({ length: TOTAL_HOURS }, (_, i) => FIRST_HOUR + i)
const SLOTS = Array.from(
  { length: TOTAL_HOURS * (60 / SLOT_MINUTES) },
  (_, i) => FIRST_HOUR * 60 + i * SLOT_MINUTES,
)

interface WeekGridProps {
  weekDays: string[]
  appointments: Appointment[]
  onSlotClick: (date: string, time: string) => void
  onAppointmentClick: (appointment: Appointment, rect: DOMRect) => void
}

function getAppointmentsForDay(appointments: Appointment[], date: string): Appointment[] {
  return appointments.filter((a) => a.appointment_date === date && a.status !== 'CANCELLED')
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
  const displayName = a.patient_name || a.full_name || 'Sem nome'
  const serviceLine = [a.service_name, a.areas].filter(Boolean).join(' · ')
  const isPartnership = a.discount_reason === 'partnership'

  return (
    <button
      type="button"
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect()
        onClick(a, rect)
      }}
      style={appointmentStyle(a)}
      className={[
        'w-full text-left rounded-md px-2 py-1 border-l-3 overflow-hidden cursor-pointer transition-opacity hover:opacity-90',
        isPartnership
          ? 'bg-amber-50 border-l-amber-400 text-amber-800'
          : 'bg-brand-50 border-l-brand-500 text-brand-900',
      ].join(' ')}
    >
      <p className="text-xs font-semibold truncate leading-tight">{displayName}</p>
      {serviceLine && (
        <p className="text-[11px] truncate leading-tight opacity-75">{serviceLine}</p>
      )}
    </button>
  )
}

export function WeekGrid({ weekDays, appointments, onSlotClick, onAppointmentClick }: WeekGridProps) {
  const today = todayStr()
  const colCount = weekDays.length
  const gridCols = `60px repeat(${colCount}, 1fr)`

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header row */}
      <div className="grid border-b border-gray-200" style={{ gridTemplateColumns: gridCols }}>
        <div className="border-r border-gray-100" />
        {weekDays.map((day) => {
          const isToday = day === today
          return (
            <div
              key={day}
              className={[
                'text-center py-2 border-r border-gray-100 last:border-r-0',
                isToday ? 'bg-brand-500 text-white' : '',
              ].join(' ')}
            >
              <p className={['text-[11px] font-medium leading-tight uppercase tracking-wide', isToday ? 'text-white/70' : 'text-gray-400'].join(' ')}>
                {shortDayName(day)}
              </p>
              <p className={['text-lg font-bold leading-tight mt-0.5', isToday ? 'text-white' : 'text-gray-800'].join(' ')}>
                {dayNumber(day)}
              </p>
              <p className={['text-[10px] font-medium leading-tight mt-0.5', isToday ? 'text-white/60' : 'text-gray-300'].join(' ')}>
                {shortMonthName(day)}
              </p>
            </div>
          )
        })}
      </div>

      {/* Time grid body */}
      <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 170px)' }}>
        <div className="grid relative pt-2" style={{ gridTemplateColumns: gridCols }}>
          {/* Time labels + horizontal lines */}
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

          {/* Day columns */}
          {weekDays.map((day) => {
            const isToday = day === today
            const dayAppts = getAppointmentsForDay(appointments, day)

            return (
              <div
                key={day}
                className={[
                  'relative border-r border-gray-100 last:border-r-0',
                  isToday ? 'bg-brand-50/30' : '',
                ].join(' ')}
                style={{ height: `${TOTAL_HOURS * HOUR_HEIGHT}px` }}
              >
                {/* 15-min grid lines + click targets */}
                {SLOTS.map((slotMin) => {
                  const h = Math.floor(slotMin / 60)
                  const m = slotMin % 60
                  const isHourLine = m === 0
                  return (
                    <button
                      type="button"
                      key={slotMin}
                      className={[
                        'absolute w-full hover:bg-brand-50/40 transition-colors cursor-pointer',
                        isHourLine ? 'border-t border-gray-100' : 'border-t border-gray-50',
                      ].join(' ')}
                      style={{
                        top: `${((slotMin - FIRST_HOUR * 60) / 60) * HOUR_HEIGHT}px`,
                        height: `${SLOT_HEIGHT}px`,
                      }}
                      onClick={() => onSlotClick(day, `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)}
                    />
                  )
                })}

                {/* Appointment blocks */}
                {dayAppts.map((a) => (
                  <AppointmentBlock
                    key={a.id}
                    appointment={a}
                    onClick={onAppointmentClick}
                  />
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
