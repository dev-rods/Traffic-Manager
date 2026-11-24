import { useState } from 'react'
import type { FormEvent } from 'react'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { formatPhoneInput, isValidPhone } from '@/utils/format'

interface PhoneStepProps {
  /** Como estava digitado (voltar não apaga). */
  defaultValue?: string
  /**
   * Chamado com o celular formatado sempre que ele fica válido (e com `null`
   * quando deixa de ser): a cotação é refeita com ele e o preço na lateral
   * vira o da pessoa (PRD 061).
   */
  onPhoneChange: (phone: string | null) => void
  onContinue: (phone: string) => void
  /** A cotação com o celular ainda não voltou: sem ela não dá para saber o ramo. */
  aguardando: boolean
}

/**
 * A etapa do celular, logo depois das áreas (PRD 061). É a primeira coisa que
 * identifica a pessoa, antes de preço fechado e datas: quem tem desconto
 * personalizado vê o valor cair aqui, não na penúltima tela.
 */
export function PhoneStep({ defaultValue = '', onPhoneChange, onContinue, aguardando }: PhoneStepProps) {
  const [phone, setPhone] = useState(defaultValue)
  const valido = isValidPhone(phone)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (valido && !aguardando) onContinue(phone)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <Input
        id="phone"
        label="Celular (WhatsApp)"
        placeholder="Digite seu celular"
        inputMode="tel"
        autoComplete="tel"
        value={phone}
        hint="Número de fora do Brasil? Comece com + e o código do país."
        onChange={(e) => {
          const formatted = formatPhoneInput(e.target.value)
          setPhone(formatted)
          onPhoneChange(isValidPhone(formatted) ? formatted : null)
        }}
      />
      <p className="text-sm text-ink-600">
        <span className="font-medium text-ink-800">Já é paciente?</span> Seu desconto aparece
        aqui assim que o celular estiver completo.
      </p>
      <Button type="submit" disabled={!valido || aguardando} loading={valido && aguardando}>
        Continuar
      </Button>
    </form>
  )
}
