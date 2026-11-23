import { useState, useEffect, useRef } from 'react'
import { Modal } from '@/components/ui/Modal'
import { DateSelect } from '@/components/ui/DateSelect'
import { Input } from '@/components/ui/Input'
import { TimeField } from './TimeField'
import { ObservacaoField } from './ObservacaoField'
import { PrimeiraVisitaField } from './PrimeiraVisitaField'
import { ehHorarioValido } from '@/lib/horario'
import { Button } from '@/components/ui/Button'
import { useCreateAppointment, useCotacao } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { calculaDuracao } from '@/lib/duracao'
import { DuracaoField } from './DuracaoField'
import { parseDuracao } from '@/lib/duracaoFixada'
import { DescontoField } from './DescontoField'
import { useDurationRules } from '@/hooks/useDurationRules'
import { useServiceAreas } from '@/hooks/useAreas'
import { usePatients, useCreatePatient } from '@/hooks/usePatients'
import { useAvailableSlots } from '@/hooks/useAvailabilityRules'
import { useDebounce } from '@/hooks/useDebounce'
import { useAuth } from '@/hooks/useAuth'
import { formatPhone } from '@/utils/formatPhone'
import { ConflitoDoMes } from './ConflitoDoMes'
import type { CreateAppointmentPayload, PatientWithStats, SessaoExistente } from '@/types'
import {
  POLITICA_DA_CLINICA,
  formataPct,
  payloadDoDesconto,
  resumoDoDesconto,
  validaDesconto,
  type DescontoEscolhido,
} from '@/lib/desconto'

interface CreateAppointmentModalProps {
  open: boolean
  initialDate?: string
  initialTime?: string
  onClose: () => void
}

export function CreateAppointmentModal({ open, initialDate, initialTime, onClose }: CreateAppointmentModalProps) {
  const { clinicId, ehAdmin } = useAuth()
  const createAppointment = useCreateAppointment()
  const { data: services } = useServices()

  const [date, setDate] = useState(initialDate ?? '')
  const [time, setTime] = useState(initialTime ?? '')
  const [notes, setNotes] = useState('')
  // Desmarcada por padrao: pelo painel a estreia e decisao da recepcao.
  const [primeiraVisita, setPrimeiraVisita] = useState(false)
  const [serviceId, setServiceId] = useState(() =>
    services?.length === 1 ? services[0].id : ''
  )
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>([])
  // Como foi digitado (PRD 050): `null` segue o cálculo, string é fixada.
  const [duracaoFixada, setDuracaoFixada] = useState<string | null>(null)
  const manualDuration = parseDuracao(duracaoFixada)
  // "Política da clínica" é o padrão (PRD 053): o backend decide com a mesma
  // função do bot e do site. A exceção é a paciente com combinado, que entra
  // em "Personalizado N%" ao ser escolhida (ver handleSelectPatient).
  const [desconto, setDesconto] = useState<DescontoEscolhido>(POLITICA_DA_CLINICA)
  const [error, setError] = useState<string | null>(null)
  // Uma sessão por mês (PRD 056): o 409 vira este aviso, no lugar dos botões.
  // PRD 056 (mesmo mês: será substituída) e PRD 060 (outro mês: pergunta).
  const [conflito, setConflito] = useState<{ existing: SessaoExistente; variante: 'mesmo_mes' | 'outro_mes' } | null>(null)
  const [preSelecionadoPelaPaciente, setPreSelecionadoPelaPaciente] = useState(false)
  const [prevServiceId, setPrevServiceId] = useState('')

  // Patient search state
  const [patientSearch, setPatientSearch] = useState('')
  const [selectedPatient, setSelectedPatient] = useState<PatientWithStats | null>(null)
  const [showResults, setShowResults] = useState(false)
  const debouncedSearch = useDebounce(patientSearch, 300)
  const resultsRef = useRef<HTMLDivElement>(null)

  // Inline patient creation state
  const [showNewPatient, setShowNewPatient] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPhone, setNewPhone] = useState('')
  const [newGender, setNewGender] = useState<'M' | 'F' | ''>('')
  const [newPatientError, setNewPatientError] = useState<string | null>(null)
  const createPatient = useCreatePatient()

  const { data: patientData } = usePatients({
    search: debouncedSearch || undefined,
    per_page: 8,
  })

  // Serviço único é escolha automática. Feito no render, como o reset de áreas
  // abaixo, para o campo não piscar vazio antes de ser preenchido.
  const [prevServices, setPrevServices] = useState(services)
  if (services !== prevServices) {
    setPrevServices(services)
    if (services?.length === 1 && !serviceId) {
      setServiceId(services[0].id)
    }
  }

  // Fetch areas for selected service
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
  const subtotal = selectedAreaIds.length > 0 && serviceAreas
    ? serviceAreas
        .filter((a) => selectedAreaIds.includes(a.area_id))
        .reduce((sum, a) => sum + a.effective_price_cents, 0)
    : undefined

  // A cotação (PRD 053): o que a política decide para ESTA paciente e ESTAS
  // áreas, pela conta do backend. Só em "Política da clínica" e com áreas.
  const telefoneDaCotacao = selectedPatient?.phone ?? (newPhone.trim() || null)
  const cotacao = useCotacao(
    desconto.modo === 'policy' && serviceId && selectedAreaIds.length > 0
      ? {
          serviceIds: [serviceId],
          serviceAreaPairs: selectedAreaIds.map((areaId) => ({ serviceId, areaId })),
          phone: telefoneDaCotacao,
        }
      : null,
  )
  const cotacaoPronta = cotacao.data ?? (cotacao.isError ? null : undefined)

  // A duração que a sessão vai de fato ocupar. Os horários vêm dela, não da
  // calculada: senão a tela oferece um horário em que a sessão não cabe.
  const duracaoEfetiva = manualDuration ?? totalDuration

  // Fetch available slots when date + service are set
  const { data: slotsData, isLoading: slotsLoading } = useAvailableSlots(
    date || undefined,
    serviceId || undefined,
    duracaoEfetiva,
  )
  const slots = slotsData?.slots ?? []

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    setSelectedAreaIds([])
    // Trocar de serviço zera as áreas, e a duração fixada foi decidida para
    // elas. Mesma razão do descarte na edição.
    setDuracaoFixada(null)
  }

  // Trocar as áreas também solta a duração fixada.
  const areasKey = [...selectedAreaIds].sort().join(',')
  const [prevAreasKey, setPrevAreasKey] = useState(areasKey)
  if (areasKey !== prevAreasKey) {
    setPrevAreasKey(areasKey)
    setDuracaoFixada(null)
  }

  // Mudou data, serviço ou áreas, os horários disponíveis mudam junto: manter a
  // hora escolhida deixaria selecionado um horário que pode não existir mais.
  const chaveDosHorarios = `${date}|${serviceId}|${duracaoEfetiva ?? ''}`
  const [prevChaveDosHorarios, setPrevChaveDosHorarios] = useState(chaveDosHorarios)
  if (chaveDosHorarios !== prevChaveDosHorarios) {
    setPrevChaveDosHorarios(chaveDosHorarios)
    if (!initialTime) setTime('')
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (resultsRef.current && !resultsRef.current.contains(e.target as Node)) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const toggleArea = (areaId: string) => {
    setSelectedAreaIds((prev) =>
      prev.includes(areaId)
        ? prev.filter((id) => id !== areaId)
        : [...prev, areaId]
    )
  }

  const handleSelectPatient = (patient: PatientWithStats) => {
    setSelectedPatient(patient)
    setPatientSearch(patient.name ?? formatPhone(patient.phone))
    setShowResults(false)
    setShowNewPatient(false)

    // Desconto combinado com a paciente entra JA SELECIONADO (decisao 8 do
    // PRD 053): e o unico caso em que "Politica da clinica" nao e o padrao. A
    // politica gravaria o mesmo (o combinado vence tudo), mas mostra-lo como
    // Personalizado deixa claro de onde veio e permite trocar.
    //
    // `!= null` e nao `?` de proposito: 0 e um combinado legitimo - "esta
    // paciente nunca recebe desconto" - e cairia fora com teste de verdade.
    //
    // Trocar para uma paciente SEM combinado volta a politica so se o modo
    // atual veio da pre-selecao: um personalizado digitado a mao fica.
    if (patient.custom_discount_pct != null) {
      setDesconto({ modo: 'custom', tipo: 'pct', texto: formataPct(patient.custom_discount_pct) })
      setPreSelecionadoPelaPaciente(true)
    } else if (preSelecionadoPelaPaciente) {
      setDesconto(POLITICA_DA_CLINICA)
      setPreSelecionadoPelaPaciente(false)
    }
  }

  const handleCreatePatient = async () => {
    if (!newName.trim() || !newPhone.trim()) {
      setNewPatientError('Nome e telefone sao obrigatorios.')
      return
    }
    setNewPatientError(null)
    try {
      const created = await createPatient.mutateAsync({
        name: newName.trim(),
        phone: newPhone.trim(),
        gender: newGender || undefined,
      })
      // Auto-select the new (or restored) patient
      const asPatientWithStats: PatientWithStats = {
        ...created.patient,
        total_visits: 0,
        last_visit: null,
        next_visit: null,
        total_spent_cents: 0,
        last_message_at: null,
        consent_status: null,
      }
      handleSelectPatient(asPatientWithStats)
      // Reset creation form
      setNewName('')
      setNewPhone('')
      setNewGender('')
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response: { data?: { message?: string } } }).response
        setNewPatientError(response.data?.message ?? 'Erro ao cadastrar paciente')
      } else {
        setNewPatientError('Erro ao cadastrar paciente')
      }
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const phone = selectedPatient?.phone
    if (!clinicId || !date || !time || !phone || !serviceId) {
      setError('Preencha todos os campos obrigatorios.')
      return
    }
    // O horário agora pode ser digitado. `<input type="time">` cobre o teclado,
    // mas não o que chega colado ou vindo de fora - e uma hora malformada só
    // apareceria como 500 no backend.
    if (!ehHorarioValido(time)) {
      setError('Horário inválido. Use o formato HH:MM.')
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

    setError(null)
    await enviar({})
  }

  /** O pedido, com o que o aviso do mesmo mês acrescentar (PRD 056). */
  const enviar = async (
    extra: Pick<CreateAppointmentPayload, 'substituir' | 'manterAsDuas' | 'motivoDasDuas' | 'remarcarExistente' | 'maisUma'>,
  ) => {
    const phone = selectedPatient?.phone
    if (!clinicId || !phone || !serviceId) return
    try {
      const serviceAreaPairs = selectedAreaIds.length > 0
        ? selectedAreaIds.map((areaId) => ({ serviceId, areaId }))
        : undefined

      await createAppointment.mutateAsync({
        clinicId,
        phone,
        serviceId,
        date,
        time,
        serviceAreaPairs,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        // Sempre enviado, inclusive `false`: omitir devolveria a decisao ao
        // backend, que e exatamente o que se reverteu.
        isFirstVisit: primeiraVisita,
        ...(manualDuration !== null ? { manualDurationMinutes: manualDuration } : {}),
        // "Política da clínica" é omitir: o backend decide (PRD 053). Os demais
        // modos opinam, inclusive "Sem desconto" (pct 0 com razão `none`).
        ...(desconto.modo === 'policy' ? {} : descontoParaCriacao(desconto)),
        ...extra,
      })
      handleClose()
    } catch (err: unknown) {
      setConflito(null)
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as {
          response: { status?: number; data?: { message?: string; code?: string; existing?: SessaoExistente } }
        }).response
        if (response.status === 409 && response.data?.code === 'SAME_MONTH_APPOINTMENT' && response.data.existing) {
          setConflito({ existing: response.data.existing, variante: 'mesmo_mes' })
          return
        }
        // Sessão futura em outro mês (PRD 060): pergunta, não bloqueio.
        if (response.status === 409 && response.data?.code === 'OTHER_MONTH_APPOINTMENT' && response.data.existing) {
          setConflito({ existing: response.data.existing, variante: 'outro_mes' })
          return
        }
        setError(response.data?.message ?? 'Erro ao criar agendamento')
      } else {
        setError('Erro ao criar agendamento')
      }
    }
  }

  /** Na criação a razão nunca é nula: `policy` nem chega aqui. */
  const descontoParaCriacao = (d: DescontoEscolhido) => {
    const { discountReason, discountPolicy: _ignorado, ...resto } = payloadDoDesconto(d)
    void _ignorado
    return { ...resto, discountReason: discountReason ?? undefined }
  }

  const handleClose = () => {
    setConflito(null)
    onClose()
  }

  const patients = patientData?.items ?? []

  return (
    <Modal open={open} onClose={handleClose} title="Novo agendamento" width="lg">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-5">
        {/* Patient search */}
        <div className="relative" ref={resultsRef}>
          <Input
            label="Paciente"
            placeholder="Buscar por nome ou telefone..."
            value={patientSearch}
            onChange={(e) => {
              setPatientSearch(e.target.value)
              setSelectedPatient(null)
              setShowResults(true)
              setShowNewPatient(false)
            }}
            onFocus={() => {
              if (patientSearch.length >= 2) setShowResults(true)
            }}
          />
          {selectedPatient && (
            <p className="text-xs text-gray-400 mt-1">
              {formatPhone(selectedPatient.phone)}
              {selectedPatient.gender && ` · ${selectedPatient.gender === 'F' ? 'Fem' : 'Masc'}`}
            </p>
          )}

          {/* Search results dropdown */}
          {showResults && debouncedSearch && debouncedSearch.length >= 2 && !showNewPatient && (
            <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-56 overflow-y-auto">
              {patients.length === 0 ? (
                <div className="px-3 py-3">
                  <p className="text-sm text-gray-400">Nenhum paciente encontrado</p>
                  <button
                    type="button"
                    onClick={() => {
                      setShowResults(false)
                      setShowNewPatient(true)
                      setNewName(debouncedSearch)
                    }}
                    className="mt-2 text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors"
                  >
                    + Cadastrar novo paciente
                  </button>
                </div>
              ) : (
                <>
                  {patients.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectPatient(p)}
                      className="w-full text-left px-3 py-2 hover:bg-gray-50 transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-800">{p.name ?? 'Sem nome'}</p>
                        <p className="text-xs text-gray-400">{formatPhone(p.phone)}</p>
                      </div>
                      {p.total_visits > 0 && (
                        <span className="text-xs text-gray-400">{p.total_visits} visitas</span>
                      )}
                    </button>
                  ))}
                  <div className="border-t border-gray-100 px-3 py-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowResults(false)
                        setShowNewPatient(true)
                      }}
                      className="text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors"
                    >
                      + Cadastrar novo paciente
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Inline patient creation form */}
        {showNewPatient && !selectedPatient && (
          <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Novo paciente</p>
              <button
                type="button"
                onClick={() => setShowNewPatient(false)}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Cancelar
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input
                placeholder="Nome"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <Input
                placeholder="Telefone"
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs text-gray-500">Genero</span>
              <div className="flex gap-1">
                {(['F', 'M'] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setNewGender(newGender === g ? '' : g)}
                    className={[
                      'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150',
                      newGender === g
                        ? 'bg-gray-900 text-white'
                        : 'bg-white border border-gray-200 text-gray-500 hover:border-gray-300',
                    ].join(' ')}
                  >
                    {g === 'F' ? 'Feminino' : 'Masculino'}
                  </button>
                ))}
              </div>
            </div>
            {newPatientError && (
              <p className="text-xs text-red-500">{newPatientError}</p>
            )}
            <Button
              className="w-full"
              onClick={() => void handleCreatePatient()}
              loading={createPatient.isPending}
            >
              Cadastrar paciente
            </Button>
          </div>
        )}

        {/* Date */}
        <DateSelect value={date} onChange={setDate} />

        {/* Service */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Servico</label>
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

        {/* Areas (shown when service has areas) */}
        {serviceId && serviceAreas && serviceAreas.length > 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">
              Areas ({selectedAreaIds.length} selecionada{selectedAreaIds.length !== 1 ? 's' : ''})
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

        <PrimeiraVisitaField checked={primeiraVisita} onChange={setPrimeiraVisita} />
        {/* O botão marca o registro; o desconto de estreia é do banco (decisão 7
            do PRD 053). Quando discordam, a pessoa vê antes de salvar. */}
        {cotacao.data && desconto.modo === 'policy' && primeiraVisita !== cotacao.data.isFirst && (
          <p className="text-xs text-amber-600" role="note">
            {primeiraVisita
              ? 'O sistema não considera esta a primeira sessão (já há sessão confirmada). A política não dá o desconto de estreia.'
              : 'Para o sistema esta é a primeira sessão: a política aplica o desconto de estreia.'}
          </p>
        )}

        <ObservacaoField value={notes} onChange={setNotes} />

        {/* Antes do horário de propósito: a duração decide quais horários cabem. */}
        <DuracaoField
          calculada={totalDuration}
          manual={duracaoFixada}
          onChange={setDuracaoFixada}
        />

        <TimeField
          value={time}
          onChange={setTime}
          slots={slots}
          loading={slotsLoading}
          enabled={Boolean(date && serviceId)}
        />

        <DescontoField
          valor={desconto}
          onChange={setDesconto}
          subtotalCents={subtotal}
          cotacao={cotacaoPronta}
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

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {conflito ? (
          <ConflitoDoMes
            existing={conflito.existing}
            novaData={date}
            novaHora={time}
            modo="criar"
            variante={conflito.variante}
            ehAdmin={Boolean(ehAdmin)}
            loading={createAppointment.isPending}
            onConfirmar={() =>
              void enviar(conflito.variante === 'outro_mes' ? { remarcarExistente: true } : { substituir: true })
            }
            onMaisUma={() => void enviar({ maisUma: true })}
            onManterAsDuas={(motivo) => void enviar({ manterAsDuas: true, motivoDasDuas: motivo })}
            onVoltar={() => setConflito(null)}
          />
        ) : (
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={handleClose}>Cancelar</Button>
            <Button type="submit" loading={createAppointment.isPending}>
              Criar agendamento
            </Button>
          </div>
        )}
      </form>
    </Modal>
  )
}
