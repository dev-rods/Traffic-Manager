import { useState } from 'react'
import type { FieldErrors, UseFormRegister, UseFormSetValue } from 'react-hook-form'
import { Input } from './ui/Input'
import { formatCpf, formatDateInput } from '@/utils/cadastro'
import type { CampoDoCadastro } from '@/types'
import type { CustomerInfoFormData } from './CustomerInfoForm'

interface CadastroFieldsProps {
  /** Só estes aparecem, na ordem CPF, nascimento, e-mail. Vazio: nada. */
  faltam: CampoDoCadastro[]
  register: UseFormRegister<CustomerInfoFormData>
  setValue: UseFormSetValue<CustomerInfoFormData>
  errors: FieldErrors<CustomerInfoFormData>
}

/**
 * Os campos do cadastro que o site pede a quem ainda não é paciente (ou tem
 * cadastro incompleto), PRD 032. Quem já tem tudo nunca vê este bloco.
 *
 * CPF e data são controlados localmente, como o celular no CustomerInfoForm:
 * `watch()` do react-hook-form não é memoizável e quebra o React Compiler.
 */
export function CadastroFields({ faltam, register, setValue, errors }: CadastroFieldsProps) {
  const [cpfDisplay, setCpfDisplay] = useState('')
  const [dateDisplay, setDateDisplay] = useState('')

  if (faltam.length === 0) return null

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-ink-200 bg-surface p-4">
      <p className="text-sm text-ink-600">
        <span className="font-medium text-ink-800">Primeira vez aqui?</span> Completamos seu
        cadastro.
      </p>
      {faltam.includes('cpf') ? (
        <Input
          id="cpf"
          label="CPF"
          placeholder="000.000.000-00"
          inputMode="numeric"
          autoComplete="off"
          value={cpfDisplay}
          error={errors.cpf?.message}
          onChange={(e) => {
            const formatted = formatCpf(e.target.value)
            setCpfDisplay(formatted)
            setValue('cpf', formatted, { shouldValidate: true })
          }}
        />
      ) : null}
      {faltam.includes('birth_date') ? (
        <Input
          id="birthDate"
          label="Data de nascimento"
          placeholder="DD/MM/AAAA"
          inputMode="numeric"
          autoComplete="bday"
          value={dateDisplay}
          error={errors.birthDate?.message}
          onChange={(e) => {
            const formatted = formatDateInput(e.target.value)
            setDateDisplay(formatted)
            setValue('birthDate', formatted, { shouldValidate: true })
          }}
        />
      ) : null}
      {faltam.includes('email') ? (
        <Input
          id="email"
          label="E-mail"
          placeholder="seu@email.com"
          inputMode="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
      ) : null}
    </div>
  )
}
