import { useState, useCallback, useMemo } from 'react'
import { useAppointments } from '@/hooks/useAppointments'
import { useAuth } from '@/hooks/useAuth'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { AgendaHeader } from './components/AgendaHeader'
import { WeekGrid } from './components/WeekGrid'
import { AppointmentPopover } from './components/AppointmentPopover'
import { CancelAppointmentModal } from './components/CancelAppointmentModal'
import { CreateAppointmentModal } from './components/CreateAppointmentModal'
import { EditAppointmentModal } from './components/EditAppointmentModal'
import { todayStr } from '@/utils/dateHelpers'
import { janelaDaAgenda } from '@/utils/agendaPaging'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import type { Appointment } from '@/types'

const PAGE_SIZE = 7

export function AgendaPage() {
  // null = ainda não navegou, então vale a página padrão (as próximas datas).
  // Guardar "não escolheu" em vez de um número evita que a página do usuário
  // seja sobrescrita quando a lista de datas recarrega.
  const [pageIndex, setPageIndex] = useState<number | null>(null)

  // Um dia sozinho, ocupando a largura toda. Sete colunas espremem um dia cheio
  // a ponto de as caixas não caberem lado a lado; aqui o mesmo dia respira.
  const [diaExpandido, setDiaExpandido] = useState<string | null>(null)

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

  // O funcionário enxerga uma janela de datas. O servidor já recusa o que está
  // fora dela; filtrar aqui evita o outro problema, que é a tela oferecer
  // colunas de dias sempre vazios e a pessoa achar que a agenda sumiu.
  const { janela: janelaDoUsuario } = useAuth()

  const allDates = useMemo(() => {
    const rules = rulesData?.data ?? []
    const dates = rules
      .filter((r) => r.rule_date !== null)
      .map((r) => r.rule_date as string)
    const unicas = [...new Set(dates)].sort()
    if (!janelaDoUsuario) return unicas
    return unicas.filter(
      (d) => d >= janelaDoUsuario.from && d <= janelaDoUsuario.to,
    )
  }, [rulesData, janelaDoUsuario])

  // A agenda abre nas próximas datas, e só nelas. O passado continua atrás do
  // botão de voltar.
  const janela = useMemo(
    () => janelaDaAgenda(allDates, todayStr(), PAGE_SIZE, pageIndex),
    [allDates, pageIndex],
  )
  const visibleDates = janela.datas

  // Expandido, a tela mostra um dia só - e a navegação passa a andar de dia em
  // dia, porque avançar sete datas de uma vez não faz sentido nesse modo.
  const indiceDoDiaExpandido = diaExpandido ? allDates.indexOf(diaExpandido) : -1
  const diasNaTela = diaExpandido ? [diaExpandido] : visibleDates

  // Fetch appointments for the visible date range
  const fetchParams = diasNaTela.length > 0
    ? { date_from: diasNaTela[0], date_to: diasNaTela[diasNaTela.length - 1] }
    : undefined

  const { data, isLoading, isError, error, refetch } = useAppointments(fetchParams)
  const appointments = data?.appointments ?? []

  // Navigation
  const handlePrev = () => {
    if (diaExpandido) {
      if (indiceDoDiaExpandido > 0) setDiaExpandido(allDates[indiceDoDiaExpandido - 1])
      return
    }
    setPageIndex(janela.pagina - 1)
  }

  const handleNext = () => {
    if (diaExpandido) {
      if (indiceDoDiaExpandido >= 0 && indiceDoDiaExpandido < allDates.length - 1) {
        setDiaExpandido(allDates[indiceDoDiaExpandido + 1])
      }
      return
    }
    setPageIndex(janela.pagina + 1)
  }

  // Volta ao padrão: o botão "Próximas" faz o mesmo que abrir a tela, e também
  // desfaz a expansão - senão ele não teria efeito visível com um dia aberto.
  const handleToday = () => {
    setPageIndex(null)
    setDiaExpandido(null)
  }

  const handleDayClick = useCallback((date: string) => {
    setDiaExpandido((atual) => (atual === date ? null : date))
  }, [])

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
    setCreateDate(diasNaTela[0] ?? todayStr())
    setCreateTime('')
    setCreateOpen(true)
  }

  return (
    <div className="p-6 pb-2 space-y-3">
      <AgendaHeader
        visibleDates={diasNaTela}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewAppointment={handleNewAppointment}
        hasPrev={diaExpandido ? indiceDoDiaExpandido > 0 : janela.podeVoltar}
        hasNext={
          diaExpandido
            ? indiceDoDiaExpandido >= 0 && indiceDoDiaExpandido < allDates.length - 1
            : janela.podeAvancar
        }
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
          weekDays={diasNaTela}
          appointments={appointments}
          onSlotClick={handleSlotClick}
          onAppointmentClick={handleAppointmentClick}
          onDayClick={handleDayClick}
          expandido={diaExpandido !== null}
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
