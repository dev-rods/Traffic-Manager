import { useState, useCallback, useMemo } from 'react'
import { useAppointments, useMarcarFalta, useDesmarcarFalta } from '@/hooks/useAppointments'
import { useToast } from '@/components/ui/toastContext'
import { useAuth } from '@/hooks/useAuth'
import { useEhDesktop } from '@/hooks/useMediaQuery'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { AgendaHeader } from './components/AgendaHeader'
import { WeekGrid } from './components/WeekGrid'
import { AgendaDoDia } from './components/AgendaDoDia'
import { AppointmentPopover } from './components/AppointmentPopover'
import { CancelAppointmentModal } from './components/CancelAppointmentModal'
import { CreateAppointmentModal } from './components/CreateAppointmentModal'
import { EditAppointmentModal } from './components/EditAppointmentModal'
import { todayStr } from '@/utils/dateHelpers'
import { janelaDaAgenda } from '@/utils/agendaPaging'
import { semFaltas, contaFaltas } from '@/lib/faltasNaAgenda'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import type { Appointment } from '@/types'

const PAGE_SIZE = 7

/** A mensagem que o servidor mandou, quando ele mandou uma.
 *
 * O backend recusa falta com motivo util (sessao ainda nao aconteceu, status
 * errado, 409 de cancelado). Engolir isso e trocar um diagnostico por
 * "erro inesperado" - e a atendente nao tem como saber o que fazer diferente.
 */
function mensagemDoErro(erro: unknown, padrao: string): string {
  const resposta = (erro as { response?: { data?: { message?: string } } })?.response
  return resposta?.data?.message ?? padrao
}

export function AgendaPage() {
  const { showToast } = useToast()
  const marcarFaltaMutation = useMarcarFalta()
  const desmarcarFaltaMutation = useDesmarcarFalta()

  // Desmarcar vem primeiro porque `marcarFalta` o usa na ação do toast.
  const desmarcarFalta = useCallback(
    (a: Appointment) => {
      desmarcarFaltaMutation.mutate(a.id, {
        onSuccess: () => showToast({ message: 'Falta desmarcada' }),
        onError: (erro) =>
          showToast({
            message: mensagemDoErro(erro, 'Nao foi possivel desmarcar a falta.'),
            variant: 'error',
          }),
      })
    },
    [desmarcarFaltaMutation, showToast],
  )

  // Marcar falta não abre modal: a ação é reversível, e a confirmação só se
  // paga quando não há volta (ver `CancelAppointmentModal`). O desfazer vive
  // no próprio toast, que é onde a atenção já está depois do clique - em vez
  // de obrigar a reabrir o popover para achar "Desmarcar falta".
  const marcarFalta = useCallback(
    (a: Appointment) => {
      marcarFaltaMutation.mutate(a.id, {
        onSuccess: () =>
          showToast({
            message: 'Falta marcada',
            action: { label: 'Desfazer', onClick: () => desmarcarFalta(a) },
          }),
        onError: (erro) =>
          showToast({
            message: mensagemDoErro(erro, 'Nao foi possivel marcar a falta.'),
            variant: 'error',
          }),
      })
    },
    [marcarFaltaMutation, showToast, desmarcarFalta],
  )

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

  /**
   * Em celular a agenda é sempre de UM dia, e em lista.
   *
   * A grade de horário foi medida e reprovada para esta tela: 15 horas a
   * 112px são 1680px, ou 2,6 telas de rolagem para ver um dia só; e um alvo de
   * toque de 44px vale 23,6 minutos de agenda, o que jogaria duas sessões
   * curtas seguidas em colunas separadas. Ver spec 015, seção 2.
   *
   * O `diaExpandido` do PR #63 continua sendo o modo de dia cheio do desktop.
   * Aqui ele vira o estado natural, e o dia mostrado é o primeiro disponível
   * quando ninguém escolheu nenhum.
   */
  const ehDesktop = useEhDesktop()
  const diaNoCelular = diaExpandido ?? visibleDates[0] ?? todayStr()
  const diaUnico = ehDesktop ? diaExpandido : diaNoCelular

  // Expandido, a tela mostra um dia só - e a navegação passa a andar de dia em
  // dia, porque avançar sete datas de uma vez não faz sentido nesse modo.
  const indiceDoDiaExpandido = diaUnico ? allDates.indexOf(diaUnico) : -1
  const diasNaTela = diaUnico ? [diaUnico] : visibleDates

  // Fetch appointments for the visible date range
  const fetchParams = diasNaTela.length > 0
    ? { date_from: diasNaTela[0], date_to: diasNaTela[diasNaTela.length - 1] }
    : undefined

  const { data, isLoading, isError, error, refetch } = useAppointments(fetchParams)
  // Memoizado porque o `?? []` cria um array NOVO a cada render enquanto a
  // query não resolve, e isso quebraria as duas memos abaixo - elas
  // recalculariam sempre, com a dependência mudando de identidade sem o
  // conteúdo mudar.
  const todosOsAgendamentos = useMemo(
    () => data?.appointments ?? [],
    [data?.appointments],
  )

  // Falta sai da agenda por padrao, como o cancelado. Decisao do Andre em
  // 04/10/2026, e o motivo e de espaco: quando o horario e reaproveitado, os
  // dois se sobrepoem e `distribuiEmColunas` da metade da largura a cada um -
  // o agendamento que importa encolhe por causa de um registro historico.
  //
  // Mas nao desaparece em silencio. Nao existe NENHUMA outra tela onde um
  // agendamento em falta seja alcancavel (nao ha historico de agendamentos do
  // paciente), entao filtrar sem dizer nada esconderia a informacao e tiraria
  // o unico caminho para "Desmarcar falta" depois que o toast passa.
  //
  // A linha so aparece quando ha falta na faixa visivel: controle permanente
  // para algo que quase sempre esta ausente e ruido, e a contagem ja e a
  // informacao que se perderia.
  const [mostrarFaltas, setMostrarFaltas] = useState(false)
  const faltasNaFaixa = useMemo(
    () => contaFaltas(todosOsAgendamentos),
    [todosOsAgendamentos],
  )
  const appointments = useMemo(
    () => (mostrarFaltas ? todosOsAgendamentos : semFaltas(todosOsAgendamentos)),
    [todosOsAgendamentos, mostrarFaltas],
  )

  // Navigation
  const handlePrev = () => {
    if (diaUnico) {
      if (indiceDoDiaExpandido > 0) setDiaExpandido(allDates[indiceDoDiaExpandido - 1])
      return
    }
    setPageIndex(janela.pagina - 1)
  }

  const handleNext = () => {
    if (diaUnico) {
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
    <div className="p-3 md:p-6 pb-2 space-y-3">
      <AgendaHeader
        visibleDates={diasNaTela}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewAppointment={handleNewAppointment}
        hasPrev={diaUnico ? indiceDoDiaExpandido > 0 : janela.podeVoltar}
        hasNext={
          diaUnico
            ? indiceDoDiaExpandido >= 0 && indiceDoDiaExpandido < allDates.length - 1
            : janela.podeAvancar
        }
      />

      {faltasNaFaixa > 0 && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span>
            {faltasNaFaixa} {faltasNaFaixa === 1 ? 'falta' : 'faltas'}
            {mostrarFaltas ? ' em exibição' : ' oculta' + (faltasNaFaixa === 1 ? '' : 's')}
          </span>
          <button
            type="button"
            onClick={() => setMostrarFaltas((v) => !v)}
            className="font-medium text-gray-500 underline decoration-gray-300 underline-offset-2 transition-colors hover:text-gray-800 cursor-pointer"
          >
            {mostrarFaltas ? 'ocultar' : 'mostrar'}
          </button>
        </div>
      )}

      {isLoading ? (
        <SkeletonTable rows={10} />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar agendamentos.'}
          onRetry={() => refetch()}
        />
      ) : (
        ehDesktop ? (
          <WeekGrid
            weekDays={diasNaTela}
            appointments={appointments}
            onSlotClick={handleSlotClick}
            onAppointmentClick={handleAppointmentClick}
            onDayClick={handleDayClick}
            expandido={diaExpandido !== null}
          />
        ) : (
          <AgendaDoDia
            dia={diaNoCelular}
            appointments={appointments}
            rules={rulesData?.data ?? []}
            onAppointmentClick={handleAppointmentClick}
          />
        )
      )}

      {/* Appointment detail popover */}
      <AppointmentPopover
        appointment={popoverAppointment}
        anchorRect={popoverRect}
        onClose={() => { setPopoverAppointment(null); setPopoverRect(null) }}
        onEdit={(a) => setEditing(a)}
        onCancel={(a) => setCancelling(a)}
        onMarcarFalta={marcarFalta}
        onDesmarcarFalta={desmarcarFalta}
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
