import { useState, useCallback, useMemo } from 'react'
import { useAppointments } from '@/hooks/useAppointments'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { AgendaHeader } from './components/AgendaHeader'
import { WeekGrid } from './components/WeekGrid'
import { AppointmentPopover } from './components/AppointmentPopover'
import { CancelAppointmentModal } from './components/CancelAppointmentModal'
import { CreateAppointmentModal } from './components/CreateAppointmentModal'
import { EditAppointmentModal } from './components/EditAppointmentModal'
import { todayStr } from '@/utils/dateHelpers'
import { paginaDaProximaData } from '@/utils/agendaPaging'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import type { Appointment } from '@/types'

const PAGE_SIZE = 7

export function AgendaPage() {
  // null = ainda não navegou, então vale a página padrão (as próximas datas).
  // Guardar "não escolheu" em vez de um número evita que a página do usuário
  // seja sobrescrita quando a lista de datas recarrega.
  const [pageIndex, setPageIndex] = useState<number | null>(null)

  // Popover state
  const [popoverAppointment, setPopoverAppointment] = useState<Appointment | null>(null)
  const [popoverRect, setPopoverRect] = useState<DOMRect | null>(null)

  // Modal state
  const [editing, setEditing] = useState<Appointment | null>(null)
  const [cancelling, setCancelling] = useState<Appointment | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createDate, setCreateDate] = useState('')
  const [createTime, setCreateTime] = useState('')

  // Fetch availability rules — only specific dates (rule_date)
  const { data: rulesData } = useAvailabilityRules()

  const allDates = useMemo(() => {
    const rules = rulesData?.data ?? []
    const dates = rules
      .filter((r) => r.rule_date !== null)
      .map((r) => r.rule_date as string)
    // Deduplicate and sort ascending
    return [...new Set(dates)].sort()
  }, [rulesData])

  // Paginate
  const totalPages = Math.max(1, Math.ceil(allDates.length / PAGE_SIZE))
  // A agenda abre no trabalho que está por vir, não no começo do histórico.
  const paginaPadrao = useMemo(
    () => paginaDaProximaData(allDates, todayStr(), PAGE_SIZE),
    [allDates],
  )
  const safePageIndex = Math.min(pageIndex ?? paginaPadrao, totalPages - 1)
  const visibleDates = allDates.slice(safePageIndex * PAGE_SIZE, (safePageIndex + 1) * PAGE_SIZE)

  // Fetch appointments for the visible date range
  const fetchParams = visibleDates.length > 0
    ? { date_from: visibleDates[0], date_to: visibleDates[visibleDates.length - 1] }
    : undefined

  const { data, isLoading, isError, error, refetch } = useAppointments(fetchParams)
  const appointments = data?.appointments ?? []

  // Navigation
  const handlePrev = () => setPageIndex(Math.max(0, safePageIndex - 1))
  const handleNext = () => setPageIndex(Math.min(totalPages - 1, safePageIndex + 1))

  // Volta ao padrão: o botão "Próximas" faz o mesmo que abrir a tela.
  const handleToday = () => setPageIndex(null)

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
    setCreateDate(visibleDates[0] ?? todayStr())
    setCreateTime('')
    setCreateOpen(true)
  }

  return (
    <div className="p-6 pb-2 space-y-3">
      <AgendaHeader
        visibleDates={visibleDates}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewAppointment={handleNewAppointment}
        hasPrev={safePageIndex > 0}
        hasNext={safePageIndex < totalPages - 1}
      />

      {isLoading ? (
        <SkeletonTable rows={10} />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar agendamentos.'}
          onRetry={() => refetch()}
        />
      ) : (
        <WeekGrid
          weekDays={visibleDates}
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
