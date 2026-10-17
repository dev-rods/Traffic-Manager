import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { formatPhoneInput, isValidBrPhone } from '@/utils/format'

const schema = z.object({
  fullName: z.string().min(2, 'Digite seu nome completo'),
  phone: z.string().refine(isValidBrPhone, 'Celular inválido'),
})

export type CustomerInfoFormData = z.infer<typeof schema>

interface CustomerInfoFormProps {
  defaultValues?: Partial<CustomerInfoFormData>
  onSubmit: (data: CustomerInfoFormData) => void
  submitting: boolean
  submitLabel?: string
  /**
   * Chamado com o celular formatado sempre que ele fica válido (e com `null`
   * quando deixa de ser) — a cotação é refeita com ele para mostrar primeira
   * sessão / desconto personalizado ANTES do clique em confirmar.
   */
  onPhoneChange?: (phone: string | null) => void
}

export function CustomerInfoForm({
  defaultValues,
  onSubmit,
  submitting,
  submitLabel = 'Finalizar',
  onPhoneChange,
}: CustomerInfoFormProps) {
  // Campo de telefone é controlado localmente (não via watch()) — react-hook-form's
  // watch() não é memoizável e quebra o React Compiler nesse componente.
  const [phoneDisplay, setPhoneDisplay] = useState(defaultValues?.phone ?? '')
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<CustomerInfoFormData>({
    resolver: zodResolver(schema),
    defaultValues: { fullName: '', phone: '', ...defaultValues },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Input
        label="Nome"
        placeholder="Digite seu nome"
        error={errors.fullName?.message}
        {...register('fullName')}
      />
      <Input
        id="phone"
        label="Celular (WhatsApp)"
        placeholder="Digite seu celular"
        inputMode="tel"
        value={phoneDisplay}
        error={errors.phone?.message}
        onChange={(e) => {
          const formatted = formatPhoneInput(e.target.value)
          setPhoneDisplay(formatted)
          setValue('phone', formatted, { shouldValidate: true })
          onPhoneChange?.(isValidBrPhone(formatted) ? formatted : null)
        }}
      />
      <Button type="submit" loading={submitting} className="mt-2">
        {submitLabel}
      </Button>
    </form>
  )
}
