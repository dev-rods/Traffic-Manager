import { useState } from 'react'
import { Input } from '@/components/ui/Input'

type Campo = 'cpf' | 'birth_date' | 'email' | 'custom_discount_pct' | 'skin_type'

interface CadastroFieldsProps {
  /** `register` do react-hook-form do formulário que embute estes campos. */
  register: (nome: Campo) => Record<string, unknown>
  errors: Partial<Record<Campo, { message?: string }>>
  /** O valor atual do desconto, para o seletor saber qual modo está ativo. */
  watch: (nome: 'custom_discount_pct') => string | undefined
  setValue: (
    nome: 'custom_discount_pct',
    valor: string,
    opcoes?: { shouldDirty?: boolean; shouldValidate?: boolean }
  ) => void
}

type ModoDesconto = 'politica' | 'parceria' | 'personalizado'

const MODOS: { key: ModoDesconto; label: string }[] = [
  { key: 'politica', label: 'Política da clínica' },
  { key: 'parceria', label: 'Parceria (100%)' },
  { key: 'personalizado', label: 'Personalizado' },
]

/**
 * Os campos de cadastro que a clínica preenche depois.
 *
 * Um componente para os dois modais - criar e editar - porque são o mesmo
 * formulário em momentos diferentes. Duplicar faria a validação divergir na
 * primeira mudança, e é validação de dado fiscal.
 */
export function CadastroFields({ register, errors, watch, setValue }: CadastroFieldsProps) {
  const valor = watch('custom_discount_pct') ?? ''
  // "Personalizado" escolhido mas ainda sem número: o campo está vazio, e só
  // o vazio não distingue "quero digitar" de "vale a política".
  const [personalizadoAberto, setPersonalizadoAberto] = useState(false)

  // O modo nasce do VALOR, não de um estado paralelo: é o que o modal de
  // editar carrega do banco, e o que vai para a API. Os três botões são os
  // mesmos do agendamento ("Parceria (100%)" ali também é só 100 gravado),
  // para a recepção não aprender duas telas.
  const modo: ModoDesconto =
    valor.trim() === ''
      ? personalizadoAberto
        ? 'personalizado'
        : 'politica'
      : Number(valor.replace(',', '.')) === 100
        ? 'parceria'
        : 'personalizado'

  const escolhe = (novo: ModoDesconto) => {
    if (novo === 'politica') {
      setValue('custom_discount_pct', '', { shouldDirty: true, shouldValidate: true })
      setPersonalizadoAberto(false)
    } else if (novo === 'parceria') {
      setValue('custom_discount_pct', '100', { shouldDirty: true, shouldValidate: true })
      setPersonalizadoAberto(false)
    } else {
      if (modo === 'parceria') {
        setValue('custom_discount_pct', '', { shouldDirty: true, shouldValidate: true })
      }
      setPersonalizadoAberto(true)
    }
  }

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
        <label htmlFor="skin_type" className="block text-sm font-medium text-gray-700 mb-1">
          Tipo de pele
        </label>
        <select
          id="skin_type"
          className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          {...register('skin_type')}
        >
          <option value="">Não informado</option>
          <option value="BRANCA">Pele branca ou clara</option>
          <option value="NEGRA">Pele morena ou negra</option>
        </select>
        <p className="text-xs text-gray-500 mt-1">
          Marcado pela profissional, presencialmente. Define qual protocolo de laser sugere os
          parâmetros no histórico de sessão.{' '}
          <strong>O bot nunca preenche nem usa este campo.</strong>
        </p>
      </div>

      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1.5">Desconto</label>
        <div className="flex gap-2" role="group" aria-label="Desconto">
          {MODOS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={modo === key}
              onClick={() => escolhe(key)}
              className={[
                'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border',
                modo === key
                  ? key === 'parceria'
                    ? 'bg-amber-50 border-amber-300 text-amber-700'
                    : key === 'personalizado'
                      ? 'bg-brand-50 border-brand-300 text-brand-700'
                      : 'bg-gray-900 border-gray-900 text-white'
                  : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </div>
        {/* O input existe sempre, para o react-hook-form não perder o campo
            quando o modo muda; só fica visível no personalizado. */}
        <div className={modo === 'personalizado' ? 'mt-2' : 'hidden'}>
          <Input
            label="Desconto personalizado (%)"
            inputMode="decimal"
            placeholder="Ex: 30"
            error={errors.custom_discount_pct?.message}
            {...register('custom_discount_pct')}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {modo === 'politica' &&
            'Valem os descontos normais da clínica: primeira sessão e faixa de áreas.'}
          {modo === 'parceria' &&
            'Todo agendamento desta paciente sai com 100% de desconto e aparece como Parceria na agenda.'}
          {modo === 'personalizado' && (
            <>
              Vale em todo agendamento desta paciente, no lugar dos descontos de primeira sessão e
              de faixa de áreas. <strong>0</strong> significa nunca dar desconto.
            </>
          )}
        </p>
      </div>
    </>
  )
}
