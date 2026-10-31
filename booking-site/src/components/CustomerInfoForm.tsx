import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { CadastroFields } from './CadastroFields'
import { formatPhoneInput, isValidBrPhone } from '@/utils/format'
import { isValidBirthDate, isValidCpf, isValidEmail } from '@/utils/cadastro'
import type { CampoDoCadastro } from '@/types'

/**
 * O schema depende do que falta no cadastro deste celular (PRD 032): o campo
 * só é exigido quando aparece. A lista vem do backend pela cotação; aqui só se
 * valida o formato, o servidor decide.
 */
function schemaPara(faltam: CampoDoCadastro[]) {
  return z.object({
    fullName: z.string().min(2, 'Digite seu nome completo'),
    phone: z.string().refine(isValidBrPhone, 'Celular inválido'),
    cpf: faltam.includes('cpf')
      ? z.string().refine(isValidCpf, 'CPF inválido')
      : z.string().optional(),
    birthDate: faltam.includes('birth_date')
      ? z.string().refine(isValidBirthDate, 'Data inválida')
      : z.string().optional(),
    email: faltam.includes('email')
      ? z.string().refine(isValidEmail, 'E-mail inválido')
      : z.string().optional(),
  })
}

export type CustomerInfoFormData = z.infer<ReturnType<typeof schemaPara>>

const SEM_CAMPOS: CampoDoCadastro[] = []

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
  /** O que falta no cadastro deste celular; só esses campos aparecem. */
  camposFaltantes?: CampoDoCadastro[]
  /** A cotação com o celular ainda não voltou: não dá para saber o que pedir. */
  aguardandoCadastro?: boolean
}

export function CustomerInfoForm({
  defaultValues,
  onSubmit,
  submitting,
  submitLabel = 'Finalizar',
  onPhoneChange,
  camposFaltantes = SEM_CAMPOS,
  aguardandoCadastro = false,
}: CustomerInfoFormProps) {
  // Campo de telefone é controlado localmente (não via watch()) — react-hook-form's
  // watch() não é memoizável e quebra o React Compiler nesse componente.
  const [phoneDisplay, setPhoneDisplay] = useState(defaultValues?.phone ?? '')
  const schema = useMemo(() => schemaPara(camposFaltantes), [camposFaltantes])
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
      <CadastroFields faltam={camposFaltantes} register={register} setValue={setValue} errors={errors} />
      <Button type="submit" loading={submitting} disabled={aguardandoCadastro} className="mt-2">
        {aguardandoCadastro ? 'Verificando cadastro...' : submitLabel}
      </Button>
    </form>
  )
}
