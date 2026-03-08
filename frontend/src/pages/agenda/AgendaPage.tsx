import { useState, useCallback } from 'react'
import { useAppointments } from '@/hooks/useAppointments'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { AgendaHeader } from './components/AgendaHeader'
import type { ViewMode } from './components/AgendaHeader'
import { WeekGrid } from './components/WeekGrid'
import { DayGrid } from './components/DayGrid'
import { AppointmentPopover } from './components/AppointmentPopover'
import { CancelAppointmentModal } from './components/CancelAppointmentModal'
import { CreateAppointmentModal } from './components/CreateAppointmentModal'
import { EditAppointmentModal } from './components/EditAppointmentModal'
import { todayStr, getWeekStart, getWeekEnd, getWeekDays, addDays } from '@/utils/dateHelpers'
import type { Appointment } from '@/types'

export function AgendaPage() {
  const [selectedDate, setSelectedDate] = useState(todayStr)
  const [viewMode, setViewMode] = useState<ViewMode>('week')
  const [weekStart, setWeekStart] = useState(() => getWeekStart(todayStr()))

  // Popover state
  const [popoverAppointment, setPopoverAppointment] = useState<Appointment | null>(null)
  const [popoverRect, setPopoverRect] = useState<DOMRect | null>(null)

  // Modal state
  const [editing, setEditing] = useState<Appointment | null>(null)
  const [cancelling, setCancelling] = useState<Appointment | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createDate, setCreateDate] = useState('')
  const [createTime, setCreateTime] = useState('')

  // Fetch appointments for the visible range
  const weekEnd = getWeekEnd(weekStart)
  const weekDays = getWeekDays(weekStart)

  const fetchParams = viewMode === 'week'
    ? { date_from: weekStart, date_to: weekEnd }
    : { date: selectedDate }

  const { data, isLoading, isError, error, refetch } = useAppointments(fetchParams)
  const appointments = data?.appointments ?? []

  // Navigation
  const handlePrev = () => {
    if (viewMode === 'week') {
      setWeekStart((ws) => addDays(ws, -7))
    } else {
      setSelectedDate((d) => {
        const newDate = addDays(d, -1)
        setWeekStart(getWeekStart(newDate))
        return newDate
      })
    }
  }

  const handleNext = () => {
    if (viewMode === 'week') {
      setWeekStart((ws) => addDays(ws, 7))
    } else {
      setSelectedDate((d) => {
        const newDate = addDays(d, 1)
        setWeekStart(getWeekStart(newDate))
        return newDate
      })
    }
  }

  const handleToday = () => {
    const today = todayStr()
    setSelectedDate(today)
    setWeekStart(getWeekStart(today))
  }

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode)
    if (mode === 'day') {
      setSelectedDate(todayStr())
    }
  }

  // Slot click → open create modal
  const handleSlotClick = useCallback((date: string, time: string) => {
    setCreateDate(date)
    setCreateTime(time)
    setCreateOpen(true)
  }, [])

  // Appointment click → show popover
  const handleAppointmentClick = useCallback((appointment: Appointment, rect: DOMRect) => {
    setPopoverAppointment(appointment)
    setPopoverRect(rect)
  }, [])

  const handleNewAppointment = () => {
    setCreateDate(viewMode === 'day' ? selectedDate : todayStr())
    setCreateTime('')
    setCreateOpen(true)
  }

  return (
    <div className="p-6 pb-2 space-y-3">
      <AgendaHeader
        weekStart={viewMode === 'week' ? weekStart : getWeekStart(selectedDate)}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewAppointment={handleNewAppointment}
      />

      {isLoading ? (
        <SkeletonTable rows={10} />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar agendamentos.'}
          onRetry={() => refetch()}
        />
      ) : viewMode === 'week' ? (
        <WeekGrid
          weekDays={weekDays}
          appointments={appointments}
          onSlotClick={handleSlotClick}
          onAppointmentClick={handleAppointmentClick}
        />
      ) : (
        <DayGrid
          date={selectedDate}
          appointments={appointments}
          onSlotClick={handleSlotClick}
          onAppointmentClick={handleAppointmentClick}
        />
      )}

      {/* Appointment detail popover */}
      <AppointmentPopover
        appointment={popoverAppointment}
        anchorRect={popoverRect}
        onClose={() => { setPopoverAppointment(null); setPopoverRect(null) }}
        onEdit={(a) => setEditing(a)}
        onCancel={(a) => setCancelling(a)}
      />

      {/* Edit appointment modal — key forces remount to reset form */}
      {editing && (
        <EditAppointmentModal
          key={editing.id}
          appointment={editing}
          onClose={() => setEditing(null)}
        />
      )}

      {/* Cancel confirmation modal */}
      <CancelAppointmentModal
        appointment={cancelling}
        onClose={() => setCancelling(null)}
      />

      {/* Create appointment modal — key forces remount to reset form */}
      {createOpen && (
        <CreateAppointmentModal
          open={createOpen}
          initialDate={createDate}
          initialTime={createTime}
          onClose={() => setCreateOpen(false)}
        />
      )}
    </div>
  )
}
