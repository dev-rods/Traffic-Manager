import { useState, useEffect, useRef } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useCreateAppointment } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { useServiceAreas } from '@/hooks/useAreas'
import { usePatients, useCreatePatient } from '@/hooks/usePatients'
import { useAvailableSlots } from '@/hooks/useAvailabilityRules'
import { useDebounce } from '@/hooks/useDebounce'
import { useAuth } from '@/hooks/useAuth'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface CreateAppointmentModalProps {
  open: boolean
  initialDate?: string
  initialTime?: string
  onClose: () => void
}

export function CreateAppointmentModal({ open, initialDate, initialTime, onClose }: CreateAppointmentModalProps) {
  const { clinicId } = useAuth()
  const createAppointment = useCreateAppointment()
  const { data: services } = useServices()

  const [date, setDate] = useState(initialDate ?? '')
  const [time, setTime] = useState(initialTime ?? '')
  const [serviceId, setServiceId] = useState(() =>
    services?.length === 1 ? services[0].id : ''
  )
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>([])
  const [discountMode, setDiscountMode] = useState<'none' | 'partnership' | 'custom'>('none')
  const [customDiscountPct, setCustomDiscountPct] = useState('')
  const [error, setError] = useState<string | null>(null)
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

  // Auto-select service when there's only one
  useEffect(() => {
    if (services?.length === 1 && !serviceId) {
      setServiceId(services[0].id)
    }
  }, [services, serviceId])

  // Fetch areas for selected service
  const { data: serviceAreas } = useServiceAreas(serviceId || undefined)

  // Compute total duration from selected areas (if any), for accurate slot calculation
  const totalDuration = selectedAreaIds.length > 0 && serviceAreas
    ? serviceAreas
        .filter((a) => selectedAreaIds.includes(a.area_id))
        .reduce((sum, a) => sum + a.effective_duration_minutes, 0)
    : undefined

  // Fetch available slots when date + service are set
  const { data: slotsData, isLoading: slotsLoading } = useAvailableSlots(
    date || undefined,
    serviceId || undefined,
    totalDuration,
  )
  const slots = slotsData?.slots ?? []

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    setSelectedAreaIds([])
  }

  // Clear selected time when date, service, or areas change (slots will change)
  useEffect(() => {
    if (!initialTime) setTime('')
  }, [date, serviceId, totalDuration, initialTime])

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
      // Auto-select the new patient
      const asPatientWithStats: PatientWithStats = {
        ...created,
        total_visits: 0,
        last_visit: null,
        next_visit: null,
        total_spent_cents: 0,
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

    setError(null)
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
        ...(discountMode === 'partnership'
          ? { discountPct: 100, discountReason: 'partnership' }
          : discountMode === 'custom' && customDiscountPct
            ? { discountPct: Number(customDiscountPct), discountReason: 'custom' }
            : {}),
      })
      handleClose()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response: { data?: { message?: string } } }).response
        setError(response.data?.message ?? 'Erro ao criar agendamento')
      } else {
        setError('Erro ao criar agendamento')
      }
    }
  }

  const handleClose = () => {
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
            <button
              type="button"
              onClick={() => void handleCreatePatient()}
              disabled={createPatient.isPending}
              className={[
                'w-full py-2 rounded-lg text-sm font-semibold transition-colors',
                createPatient.isPending
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-900 text-white hover:bg-brand-600',
              ].join(' ')}
            >
              {createPatient.isPending ? 'Cadastrando...' : 'Cadastrar paciente'}
            </button>
          </div>
        )}

        {/* Date */}
        <Input
          label="Data"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

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

        {/* Time slot picker */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Horario</label>
          {!date || !serviceId ? (
            <p className="text-sm text-gray-300 py-3">Selecione data e servico para ver horarios</p>
          ) : slotsLoading ? (
            <div className="flex items-center gap-2 py-3">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-400">Carregando horarios...</span>
            </div>
          ) : slots.length === 0 ? (
            <p className="text-sm text-gray-400 py-3">Nenhum horario disponivel para esta data</p>
          ) : (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
              {slots.map((slot) => (
                <button
                  key={slot}
                  type="button"
                  onClick={() => setTime(slot)}
                  className={[
                    'px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                    time === slot
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                  ].join(' ')}
                >
                  {slot}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Discount section */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">Desconto</label>
          <div className="flex gap-2">
            {([
              { key: 'none', label: 'Sem desconto' },
              { key: 'partnership', label: 'Parceria (100%)' },
              { key: 'custom', label: 'Personalizado' },
            ] as const).map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setDiscountMode(key)}
                className={[
                  'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border',
                  discountMode === key
                    ? key === 'partnership'
                      ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : key === 'custom'
                        ? 'bg-brand-50 border-brand-300 text-brand-700'
                        : 'bg-gray-900 border-gray-900 text-white'
                    : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600',
                ].join(' ')}
              >
                {label}
              </button>
            ))}
          </div>
          {discountMode === 'custom' && (
            <div className="mt-2 flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="99"
                placeholder="Ex: 30"
                value={customDiscountPct}
                onChange={(e) => setCustomDiscountPct(e.target.value)}
                className="w-24 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
              <span className="text-sm text-gray-500">% de desconto</span>
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2.5 text-sm font-medium text-gray-500 hover:text-gray-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={createAppointment.isPending}
            className={[
              'px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              createAppointment.isPending
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-gray-900 hover:bg-brand-600 text-white',
            ].join(' ')}
          >
            {createAppointment.isPending ? 'Criando...' : 'Criar agendamento'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
