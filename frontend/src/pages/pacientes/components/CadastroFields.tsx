import { Input } from '@/components/ui/Input'

interface CadastroFieldsProps {
  /** `register` do react-hook-form do formulário que embute estes campos. */
  register: (nome: 'cpf' | 'birth_date' | 'email') => Record<string, unknown>
  errors: Partial<Record<'cpf' | 'birth_date' | 'email', { message?: string }>>
}

/**
 * Os campos de cadastro que a clínica preenche depois.
 *
 * Um componente para os dois modais - criar e editar - porque são o mesmo
 * formulário em momentos diferentes. Duplicar faria a validação divergir na
 * primeira mudança, e é validação de dado fiscal.
 */
export function CadastroFields({ register, errors }: CadastroFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="CPF"
          placeholder="000.000.000-00"
          inputMode="numeric"
          error={errors.cpf?.message}
          {...register('cpf')}
        />
        <Input
          label="Nascimento"
          type="date"
          error={errors.birth_date?.message}
          {...register('birth_date')}
        />
      </div>
      <Input
        label="E-mail"
        type="email"
        placeholder="opcional"
        error={errors.email?.message}
        {...register('email')}
      />
    </>
  )
}
