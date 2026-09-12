import { Input } from '@/components/ui/Input'

interface CadastroFieldsProps {
  /** `register` do react-hook-form do formulário que embute estes campos. */
  register: (
    nome: 'cpf' | 'birth_date' | 'email' | 'custom_discount_pct',
  ) => Record<string, unknown>
  errors: Partial<
    Record<'cpf' | 'birth_date' | 'email' | 'custom_discount_pct', { message?: string }>
  >
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
      <div>
        <Input
          label="Desconto personalizado (%)"
          inputMode="numeric"
          placeholder="deixe vazio para usar a politica da clinica"
          error={errors.custom_discount_pct?.message}
          {...register('custom_discount_pct')}
        />
        <p className="text-xs text-gray-500 mt-1">
          Preenchido, vale em todo agendamento desta paciente, no lugar dos
          descontos de primeira sessao e de faixa de areas. Vazio usa a politica
          normal; <strong>0</strong> significa nunca dar desconto.
        </p>
      </div>
    </>
  )
}
