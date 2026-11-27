import { useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { CadastroFields } from './CadastroFields'
import { CelularComPais } from './CelularComPais'
import { isValidPhone } from '@/utils/format'
import { isValidBirthDate, isValidCpf, isValidEmail } from '@/utils/cadastro'
import type { CampoDoCadastro } from '@/types'

/**
 * O schema depende do que falta no cadastro deste celular (PRD 032): o campo
 * só é exigido quando aparece. A lista vem do backend pela cotação; aqui só se
 * valida o formato, o servidor decide.
 */
function schemaPara(faltam: CampoDoCadastro[], semNome = false, semCelular = false) {
  return z.object({
    fullName: semNome ? z.string().optional() : z.string().min(2, 'Digite seu nome completo'),
    phone: semCelular ? z.string().optional() : z.string().refine(isValidPhone, 'Celular inválido'),
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
  /** PRD 061: o celular já foi digitado na etapa anterior; o campo some. */
  semCelular?: boolean
  /** PRD 061: o nome veio do cadastro (é você?); o campo some. */
  semNome?: boolean
}

export function CustomerInfoForm({
  defaultValues,
  onSubmit,
  submitting,
  submitLabel = 'Finalizar',
  onPhoneChange,
  camposFaltantes = SEM_CAMPOS,
  aguardandoCadastro = false,
  semCelular = false,
  semNome = false,
}: CustomerInfoFormProps) {
  // Campo de telefone é controlado localmente (não via watch()) — react-hook-form's
  // watch() não é memoizável e quebra o React Compiler nesse componente.
  const schema = useMemo(
    () => schemaPara(camposFaltantes, semNome, semCelular),
    [camposFaltantes, semNome, semCelular]
  )
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
      {semNome ? null : (
        <Input
          label="Nome"
          placeholder="Digite seu nome"
          error={errors.fullName?.message}
          {...register('fullName')}
        />
      )}
      {semCelular ? null : (
      <CelularComPais
        id="phone"
        defaultValue={defaultValues?.phone ?? ''}
        error={errors.phone?.message}
        onChange={(valor) => {
          setValue('phone', valor, { shouldValidate: true })
          onPhoneChange?.(isValidPhone(valor) ? valor : null)
        }}
      />
      )}
      <CadastroFields faltam={camposFaltantes} register={register} setValue={setValue} errors={errors} />
      <Button type="submit" loading={submitting} disabled={aguardandoCadastro} className="mt-2">
        {aguardandoCadastro ? 'Verificando cadastro...' : submitLabel}
      </Button>
    </form>
  )
}
