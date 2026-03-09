import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUpdatePatient } from '@/hooks/usePatients'
import { normalizePhone } from '@/utils/normalizePhone'
import type { PatientWithStats } from '@/types'

const schema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  phone: z.string().min(10, 'Telefone invalido').max(20, 'Telefone invalido'),
  gender: z.enum(['M', 'F']).optional(),
})

type FormData = z.infer<typeof schema>

interface EditPatientModalProps {
  patient: PatientWithStats | null
  onClose: () => void
}

export function EditPatientModal({ patient, onClose }: EditPatientModalProps) {
  const updatePatient = useUpdatePatient()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  useEffect(() => {
    if (patient) {
      reset({
        name: patient.name ?? '',
        phone: patient.phone,
        gender: (patient.gender as 'M' | 'F') ?? undefined,
      })
    }
  }, [patient, reset])

  const onSubmit = async (data: FormData) => {
    if (!patient) return
    setServerError(null)
    try {
      await updatePatient.mutateAsync({
        patientId: patient.id,
        data: {
          name: data.name,
          phone: normalizePhone(data.phone),
          gender: data.gender as 'M' | 'F',
        },
      })
      onClose()
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as Record<string, unknown>).response
      ) {
        const response = (err as { response: { data?: { message?: string } } }).response
        setServerError(response.data?.message ?? 'Erro ao atualizar paciente')
      } else {
        setServerError('Erro ao atualizar paciente')
      }
    }
  }

  const handleClose = () => {
    setServerError(null)
    onClose()
  }

  return (
    <Modal open={!!patient} onClose={handleClose} title="Editar paciente">
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4">
        <Input
          label="Nome completo"
          placeholder="Maria Silva"
          error={errors.name?.message}
          {...register('name')}
        />

        <Input
          label="WhatsApp"
          placeholder="+5511999999999"
          error={errors.phone?.message}
          {...register('phone')}
        />

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-2">Sexo</label>
          <div className="flex gap-3">
            {(['F', 'M'] as const).map((g) => (
              <label key={g} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value={g}
                  {...register('gender')}
                  className="accent-brand-500"
                />
                <span className="text-sm text-gray-700">
                  {g === 'F' ? 'Feminino' : 'Masculino'}
                </span>
              </label>
            ))}
          </div>
        </div>

        {serverError && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            {serverError}
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
            disabled={isSubmitting}
            className={[
              'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              isSubmitting
                ? 'bg-brand-300 text-white cursor-not-allowed'
                : 'bg-brand-500 hover:bg-brand-600 text-white',
            ].join(' ')}
          >
            {isSubmitting ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
