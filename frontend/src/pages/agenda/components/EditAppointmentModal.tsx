import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { DateSelect } from '@/components/ui/DateSelect'
import { Button } from '@/components/ui/Button'
import { useUpdateAppointment, useCotacao } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { calculaDuracao } from '@/lib/duracao'
import { precisaMandarDuracao } from '@/lib/duracaoNoPedido'
import { useDurationRules } from '@/hooks/useDurationRules'
import { useServiceAreas } from '@/hooks/useAreas'
import { useAvailableSlots } from '@/hooks/useAvailabilityRules'
import { DuracaoField } from './DuracaoField'
import { parseDuracao } from '@/lib/duracaoFixada'
import { DescontoField } from './DescontoField'
import { TimeField } from './TimeField'
import { ObservacaoField } from './ObservacaoField'
import { PrimeiraVisitaField } from './PrimeiraVisitaField'
import { ehHorarioValido } from '@/lib/horario'
import { ResumoDaAlteracao } from './ResumoDaAlteracao'
import {
  avisosDaAlteracao,
  linhasDaAlteracao,
  temEfeitoForaDaTela,
  textoDoDesconto,
  type AlteracaoPretendida,
} from '@/lib/alteracaoDeAgendamento'
import type { Appointment, UpdateAppointmentPayload } from '@/types'
import {
  descontoDoAgendamento,
  payloadDoDesconto,
  resumoDoDesconto,
  validaDesconto,
  type DescontoEscolhido,
} from '@/lib/desconto'

interface EditAppointmentModalProps {
  appointment: Appointment | null
  onClose: () => void
}

export function EditAppointmentModal({ appointment, onClose }: EditAppointmentModalProps) {
  const updateAppointment = useUpdateAppointment()
  const { data: services } = useServices()

  const initialAreaIds = appointment?.area_ids?.split(',') ?? []

  const [date, setDate] = useState(appointment?.appointment_date ?? '')
  const [time, setTime] = useState(appointment?.start_time.slice(0, 5) ?? '')
  const [notes, setNotes] = useState(appointment?.notes ?? '')
  const [primeiraVisita, setPrimeiraVisita] = useState(appointment?.is_first_visit ?? false)
  const [serviceId, setServiceId] = useState(appointment?.service_id ?? '')
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>(initialAreaIds)
  const [prevServiceId, setPrevServiceId] = useState(serviceId)
  // Como foi digitado (PRD 050): `null` segue o cálculo, string é fixada,
  // inclusive vazia. O número só é exigido ao salvar.
  const [duracaoFixada, setDuracaoFixada] = useState<string | null>(
    appointment?.manual_duration_minutes == null ? null : String(appointment.manual_duration_minutes)
  )
  const manualDuration = parseDuracao(duracaoFixada)
  const [duracaoDescartada, setDuracaoDescartada] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Segundo passo DENTRO do mesmo modal (PRD 043): dois overlays empilhados
  // escondem o formulário que a pessoa precisa poder revisar.
  const [confirmando, setConfirmando] = useState(false)

  // Desconto, nas duas formas (PRD 050). O gravado é a referência do "mudou".
  const descontoGravado: DescontoEscolhido = appointment
    ? descontoDoAgendamento(appointment)
    : { modo: 'none', tipo: 'pct', texto: '' }
  const [desconto, setDesconto] = useState<DescontoEscolhido>(descontoGravado)

  // "Política da clínica" na edição (PRD 053): a cotação mostra o que a
  // política decide para as áreas ATUAIS do formulário.
  const cotacao = useCotacao(
    appointment && desconto.modo === 'policy' && serviceId && selectedAreaIds.length > 0
      ? {
          serviceIds: [serviceId],
          serviceAreaPairs: selectedAreaIds.map((areaId) => ({ serviceId, areaId })),
          phone: appointment.patient_phone ?? null,
        }
      : null,
  )

  const { data: serviceAreas } = useServiceAreas(serviceId || undefined)
  const { data: durationRulesData } = useDurationRules()
  const durationRules = durationRulesData?.duration_rules

  const somaDasAreas = selectedAreaIds.length > 0 && serviceAreas
    ? serviceAreas
        .filter((a) => selectedAreaIds.includes(a.area_id))
        .reduce((sum, a) => sum + a.effective_duration_minutes, 0)
    : undefined
  // Preview: o backend reaplica a mesma regra antes de devolver horários.
  const totalDuration =
    somaDasAreas === undefined ? undefined : calculaDuracao(somaDasAreas, durationRules)
  // A duração que a sessão vai de fato ocupar. Os horários têm de ser buscados
  // com ela, não com a calculada: senão a tela oferece um horário em que a
  // sessão não cabe, e o conflito só aparece ao salvar. Texto fixado ainda
  // inválido (vazio, fora da faixa) cai na calculada: nunca NaN no pedido.
  const duracaoEfetiva = manualDuration ?? totalDuration

  // Fetch available slots
  const { data: slotsData, isLoading: slotsLoading } = useAvailableSlots(
    date || undefined,
    serviceId || undefined,
    duracaoEfetiva,
  )
  const slots = slotsData?.slots ?? []

  // Include the current appointment's time in the slot list (it's "available" for itself)
  const currentSlot = appointment?.start_time.slice(0, 5) ?? ''
  const slotsWithCurrent = slots.includes(currentSlot)
    ? slots
    : currentSlot && date === appointment?.appointment_date
      ? [currentSlot, ...slots].sort()
      : slots

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    if (prevServiceId !== '') {
      setSelectedAreaIds([])
    }
  }

  // Clear selected time when date, service, or areas change (derived state pattern)
  const [prevSlotKey, setPrevSlotKey] = useState(`${date}|${serviceId}|${duracaoEfetiva}`)
  const slotKey = `${date}|${serviceId}|${duracaoEfetiva}`
  if (slotKey !== prevSlotKey) {
    setPrevSlotKey(slotKey)
    if (date !== appointment?.appointment_date) {
      setTime('')
    }
  }

  // Trocar as áreas DESCARTA a duração fixada: ela foi decidida para outro
  // conjunto de áreas. O backend faz o mesmo em update_appointment_services, e
  // a tela precisa concordar - senão ela promete 50 min e o servidor grava 30.
  const areasKey = [...selectedAreaIds].sort().join(',')
  const [prevAreasKey, setPrevAreasKey] = useState(areasKey)
  if (areasKey !== prevAreasKey) {
    setPrevAreasKey(areasKey)
    if (duracaoFixada !== null) {
      setDuracaoFixada(null)
      setDuracaoDescartada(true)
    }
  }

  if (!appointment) return null

  const a = appointment
  const displayName = a.patient_name || a.full_name || 'Sem nome'

  const dateChanged = date !== a.appointment_date
  const timeChanged = time !== a.start_time.slice(0, 5)
  const notesChanged = notes !== (a.notes ?? '')
  const primeiraChanged = primeiraVisita !== (a.is_first_visit ?? false)
  const serviceChanged = serviceId !== a.service_id
  const areasChanged = (() => {
    const sorted = [...selectedAreaIds].sort()
    const origSorted = [...initialAreaIds].sort()
    return sorted.length !== origSorted.length || sorted.some((v, i) => v !== origSorted[i])
  })()
  // Em "Política da clínica", trocar áreas ou serviço conta como mudança de
  // desconto: a faixa por quantidade de áreas depende das áreas, e o backend
  // re-decide ao salvar (decisão 5 do PRD 053).
  const discountChanged =
    desconto.modo === 'policy'
      ? descontoGravado.modo !== 'policy' || areasChanged || serviceChanged
      : JSON.stringify(payloadDoDesconto(desconto)) !== JSON.stringify(payloadDoDesconto(descontoGravado))

  // Fixada e apagada conta como mudança: é o que deixa o Salvar acusar.
  const manualChanged =
    duracaoFixada === null
      ? a.manual_duration_minutes != null
      : manualDuration !== (a.manual_duration_minutes ?? null)

  const subtotal = selectedAreaIds.length > 0 && serviceAreas
    ? serviceAreas
        .filter((ar) => selectedAreaIds.includes(ar.area_id))
        .reduce((sum, ar) => sum + ar.effective_price_cents, 0)
    : undefined

  /**
   * Trocar a área faz o servidor DESCARTAR o override, a menos que o pedido
   * traga uma duração. Então, nesse caminho, repetir o mesmo número não é
   * "não mudou" - é preciso reafirmar.
   *
   * Sem isto (relatado em 21/09/2026): fixa 10, remove uma área, redigita 10,
   * e o pedido sai calado. O servidor recalcula pelas áreas e recusa por
   * conflito, com a tela ainda mostrando 10.
   */
  const mandaDuracao = precisaMandarDuracao({
    manualNaTela: manualDuration,
    manualNoServidor: a.manual_duration_minutes ?? null,
    mudouAreaOuServico: serviceChanged || areasChanged,
  })

  const hasChanges = dateChanged || timeChanged || primeiraChanged || notesChanged || serviceChanged || areasChanged || discountChanged || manualChanged

  // O que vai mudar, em texto legível, para o resumo do PRD 043. Observação e
  // primeira visita não entram: não têm efeito fora da tela.
  const nomeDoServico = (id: string) =>
    services?.find((s) => s.id === id)?.name ?? id
  const nomesDasAreas = (ids: string[]) => {
    const nomes = ids
      .map((id) => serviceAreas?.find((ar) => ar.area_id === id)?.name)
      .filter((n): n is string => Boolean(n))
    return nomes.length > 0 ? nomes.join(', ') : 'nenhuma'
  }
  const alteracao: AlteracaoPretendida = {
    ...(dateChanged ? { data: { de: a.appointment_date, para: date } } : {}),
    ...(timeChanged ? { horario: { de: a.start_time.slice(0, 5), para: time } } : {}),
    ...(serviceChanged
      ? { servico: { de: a.service_name ?? nomeDoServico(a.service_id), para: nomeDoServico(serviceId) } }
      : {}),
    ...(areasChanged
      ? { areas: { de: a.areas || 'nenhuma', para: nomesDasAreas(selectedAreaIds) } }
      : {}),
    ...(manualChanged
      ? {
          duracao: {
            de: a.manual_duration_minutes ? `${a.manual_duration_minutes} min` : 'calculada',
            para: manualDuration ? `${manualDuration} min` : 'calculada',
          },
        }
      : {}),
    ...(discountChanged
      ? {
          desconto: {
            de: textoDoDesconto(descontoGravado, { discountReason: a.discount_reason, discountPct: a.discount_pct }),
            para: textoDoDesconto(desconto, cotacao.data),
          },
        }
      : {}),
  }
  const pedeConfirmacao = temEfeitoForaDaTela(alteracao)

  const toggleArea = (areaId: string) => {
    setSelectedAreaIds((prev) =>
      prev.includes(areaId)
        ? prev.filter((id) => id !== areaId)
        : [...prev, areaId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (time && !ehHorarioValido(time)) {
      setError('Horário inválido. Use o formato HH:MM.')
      return
    }
    if (!date || !time) {
      setError('Data e horário são obrigatórios.')
      return
    }

    if (!serviceId) {
      setError('Selecione um serviço.')
      return
    }

    // A obrigação de a duração fixada ter número é daqui, não do campo (PRD 050).
    if (duracaoFixada !== null && manualDuration === null) {
      setError('Informe a duração fixada entre 5 e 480 minutos, ou volte ao cálculo.')
      return
    }

    const erroDesconto = validaDesconto(desconto, subtotal)
    if (erroDesconto) {
      setError(erroDesconto)
      return
    }

    if (!hasChanges) {
      onClose()
      return
    }

    // A porta do PRD 043: mudança com efeito fora da tela não executa no
    // clique. Mostra o que vai mudar e espera o segundo gesto. Observação e
    // primeira visita seguem direto - confirmação que não compra nada treina
    // a clicar sem ler.
    if (pedeConfirmacao && !confirmando) {
      setError(null)
      setConfirmando(true)
      return
    }

    await executa()
  }

  /** Grava. Chamado pelo Salvar (sem campo sensível) e pelo Confirmar. */
  const executa = async () => {
    setError(null)
    try {
      const payload: UpdateAppointmentPayload = {}

      // `null` explícito é o que SOLTA o override no backend; omitir não mexe.
      if (mandaDuracao) payload.manualDurationMinutes = manualDuration
      if (dateChanged) payload.date = date
      if (timeChanged) payload.time = time
      if (notesChanged) payload.notes = notes
      if (primeiraChanged) payload.isFirstVisit = primeiraVisita

      if (serviceChanged || areasChanged) {
        payload.serviceId = serviceId
        if (selectedAreaIds.length > 0) {
          payload.serviceAreaPairs = selectedAreaIds.map((areaId) => ({
            serviceId,
            areaId,
          }))
        }
      }

      if (discountChanged) Object.assign(payload, payloadDoDesconto(desconto))

      await updateAppointment.mutateAsync({
        appointmentId: a.id,
        payload,
      })
      onClose()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response: { data?: { message?: string; error?: string } } }).response
        const detail = response.data?.error || response.data?.message
        setError(detail ?? 'Erro ao atualizar agendamento')
      } else {
        setError('Erro ao atualizar agendamento')
      }
    }
  }

  if (confirmando) {
    return (
      <Modal open onClose={onClose} title="Confirmar alteração" width="lg">
        <ResumoDaAlteracao
          paciente={displayName}
          quando={`${a.appointment_date} às ${a.start_time.slice(0, 5)}`}
          linhas={linhasDaAlteracao(alteracao)}
          avisos={avisosDaAlteracao(a, alteracao)}
          onVoltar={() => setConfirmando(false)}
          onConfirmar={() => void executa()}
          salvando={updateAppointment.isPending}
          erro={error}
        />
      </Modal>
    )
  }

  return (
    <Modal open onClose={onClose} title="Editar agendamento" width="lg">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-5">
        {/* Patient info (read-only) */}
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-sm font-medium text-gray-800">{displayName}</p>
        </div>

        {/* Date */}
        <DateSelect value={date} onChange={setDate}
          includePast />

        {/* Service */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Serviço</label>
          <select
            value={serviceId}
            onChange={(e) => setServiceId(e.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          >
            <option value="">Selecione...</option>
            {services?.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Areas */}
        {serviceId && serviceAreas && serviceAreas.length > 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">
              Áreas ({selectedAreaIds.length} selecionada{selectedAreaIds.length !== 1 ? 's' : ''})
            </label>
            <div className="rounded-lg border border-gray-200 divide-y divide-gray-100 max-h-40 overflow-y-auto">
              {serviceAreas.map((area) => (
                <label
                  key={area.area_id}
                  className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedAreaIds.includes(area.area_id)}
                      onChange={() => toggleArea(area.area_id)}
                      className="accent-brand-500"
                    />
                    <span className="text-sm text-gray-800">{area.name}</span>
                  </div>
                  {area.effective_price_cents > 0 && (
                    <span className="text-xs text-gray-400">
                      {(area.effective_price_cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </span>
                  )}
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Antes do horário de propósito: a duração decide quais horários cabem. */}
        <DuracaoField
          calculada={totalDuration}
          manual={duracaoFixada}
          onChange={(v) => {
            setDuracaoFixada(v)
            setDuracaoDescartada(false)
          }}
          avisoDeDescarte={duracaoDescartada}
        />

        <TimeField
          value={time}
          onChange={setTime}
          slots={slotsWithCurrent}
          loading={slotsLoading}
          enabled={Boolean(date && serviceId)}
        />

        <DescontoField
          valor={desconto}
          onChange={setDesconto}
          subtotalCents={subtotal}
          cotacao={cotacao.data ?? (cotacao.isError ? null : undefined)}
          cotando={cotacao.isPending && cotacao.fetchStatus === 'fetching'}
          erroDaCotacao={cotacao.isError}
        />

        {/* Price summary */}
        {subtotal !== undefined && (() => {
          const resumo = resumoDoDesconto(desconto, subtotal, cotacao.data)
          const fmt = (v: number) => (v / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

          return (
            <div className="rounded-lg bg-gray-50 px-4 py-3 space-y-1.5">
              <div className="flex justify-between text-sm text-gray-500">
                <span>{selectedAreaIds.length} área{selectedAreaIds.length !== 1 ? 's' : ''}</span>
                <span>{fmt(subtotal)}</span>
              </div>
              {resumo && (
                <div className="flex justify-between text-sm text-amber-600">
                  <span>Desconto ({resumo.rotulo})</span>
                  <span>-{fmt(resumo.descontoCents)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm font-semibold text-gray-900 border-t border-gray-200 pt-1.5">
                <span>Total</span>
                <span>{fmt(resumo ? resumo.totalCents : subtotal)}</span>
              </div>
            </div>
          )
        })()}

        <PrimeiraVisitaField checked={primeiraVisita} onChange={setPrimeiraVisita} />

        <ObservacaoField value={notes} onChange={setNotes} />

        {/* Reschedule warning */}
        {(dateChanged || timeChanged) && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-4 py-3">
            O agendamento será reagendado para <strong>{date}</strong> às <strong>{time}</strong>.
            Até 15 minutos de sobreposição com a sessão vizinha são aceitos; acima disso o
            servidor recusa.
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={updateAppointment.isPending} disabled={!hasChanges}>
            Salvar alterações
          </Button>
        </div>
      </form>
    </Modal>
  )
}
