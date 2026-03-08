import { useState, useEffect, useRef } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useCreateAppointment } from '@/hooks/useAppointments'
import { useServices } from '@/hooks/useServices'
import { useServiceAreas } from '@/hooks/useAreas'
import { usePatients } from '@/hooks/usePatients'
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
  const [serviceId, setServiceId] = useState('')
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [prevServiceId, setPrevServiceId] = useState('')

  // Patient search state
  const [patientSearch, setPatientSearch] = useState('')
  const [selectedPatient, setSelectedPatient] = useState<PatientWithStats | null>(null)
  const [showResults, setShowResults] = useState(false)
  const debouncedSearch = useDebounce(patientSearch, 300)
  const resultsRef = useRef<HTMLDivElement>(null)

  const { data: patientData } = usePatients({
    search: debouncedSearch || undefined,
    per_page: 8,
  })

  // Fetch areas for selected service
  const { data: serviceAreas } = useServiceAreas(serviceId || undefined)

  // Reset areas when service changes (derived state pattern)
  if (serviceId !== prevServiceId) {
    setPrevServiceId(serviceId)
    setSelectedAreaIds([])
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
    <Modal open={open} onClose={handleClose} title="Novo agendamento">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {/* Date + Time */}
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Data"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <Input
            label="Horario"
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </div>

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
          {showResults && debouncedSearch && debouncedSearch.length >= 2 && (
            <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-48 overflow-y-auto">
              {patients.length === 0 ? (
                <p className="px-3 py-2 text-sm text-gray-400">Nenhum paciente encontrado</p>
              ) : (
                patients.map((p) => (
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
                ))
              )}
            </div>
          )}
        </div>

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

        {/* Areas (shown when service is selected and has areas) */}
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

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={createAppointment.isPending}
            className={[
              'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              createAppointment.isPending
                ? 'bg-brand-300 text-white cursor-not-allowed'
                : 'bg-brand-500 hover:bg-brand-600 text-white',
            ].join(' ')}
          >
            {createAppointment.isPending ? 'Criando...' : 'Criar agendamento'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
