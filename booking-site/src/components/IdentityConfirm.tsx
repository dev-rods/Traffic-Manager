import { useState } from 'react'
import { Button } from './ui/Button'
import { CustomerInfoForm } from './CustomerInfoForm'
import type { CustomerInfoFormData } from './CustomerInfoForm'
import type { CampoDoCadastro } from '@/types'

interface IdentityConfirmProps {
  /** Primeiro nome, vindo do backend DEPOIS do código confirmado. */
  nome: string
  /** O que falta no cadastro; aparece só depois de "Sou eu". */
  faltam: CampoDoCadastro[]
  onConfirm: (dados: Partial<Pick<CustomerInfoFormData, 'cpf' | 'birthDate' | 'email'>>) => void
  onNotMe: () => void
  submitting: boolean
  error?: string | null
}

/**
 * "Olá, Edna, é você?" (PRD 061). Só existe depois do código: antes dele a API
 * nunca devolve nome. O nome não é editável aqui, porque quem está no sistema
 * foi conferido pela clínica; o que falta no cadastro é pedido em seguida.
 */
export function IdentityConfirm({ nome, faltam, onConfirm, onNotMe, submitting, error }: IdentityConfirmProps) {
  const [souEu, setSouEu] = useState(false)
  const precisaCompletar = faltam.length > 0

  if (souEu && precisaCompletar) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-ink-700">
          Olá, <span className="font-semibold text-ink-900">{nome}</span>! Falta pouco para o seu
          cadastro ficar completo.
        </p>
        <CustomerInfoForm
          semNome
          semCelular
          camposFaltantes={faltam}
          onSubmit={(dados) => onConfirm({ cpf: dados.cpf, birthDate: dados.birthDate, email: dados.email })}
          submitting={submitting}
          submitLabel="Continuar"
        />
        {error ? (
          <p role="alert" className="text-sm text-danger-500">
            {error}
          </p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-lg text-ink-800">
        Olá, <span className="font-semibold text-ink-900">{nome}</span>! É você?
      </p>
      <p className="text-sm text-ink-600">Encontramos seu cadastro pelo celular informado.</p>
      <Button
        onClick={() => {
          if (precisaCompletar) setSouEu(true)
          else onConfirm({})
        }}
        loading={submitting && !precisaCompletar}
      >
        Sou eu
      </Button>
      <button
        type="button"
        onClick={onNotMe}
        className="h-11 cursor-pointer rounded-lg text-sm font-medium text-ink-500 transition-colors hover:text-ink-900"
      >
        Não sou eu
      </button>
      {error ? (
        <p role="alert" className="text-sm text-danger-500">
          {error}
        </p>
      ) : null}
    </div>
  )
}
