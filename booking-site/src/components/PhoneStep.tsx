import { useState } from 'react'
import type { FormEvent } from 'react'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { formatPhoneInput, isValidPhone } from '@/utils/format'

interface PhoneStepProps {
  /** Como estava digitado (voltar não apaga). */
  defaultValue?: string
  onContinue: (phone: string) => void
  /** O site ainda está conferindo a sessão já verificada nesta aba. */
  aguardando: boolean
}

/**
 * A etapa do celular, logo depois das áreas (PRD 061). É a primeira coisa que
 * identifica a pessoa, antes de preço fechado e datas. Aqui a lateral ainda
 * mostra a tabela: o preço da pessoa só aparece depois do código, senão
 * qualquer um veria o desconto de outra só digitando o número dela.
 */
export function PhoneStep({ defaultValue = '', onContinue, aguardando }: PhoneStepProps) {
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
        onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
      />
      <p className="text-sm text-ink-600">
        Vamos enviar um código por WhatsApp para confirmar que é você e conferir se há{' '}
        <span className="font-medium text-ink-800">desconto personalizado</span> no seu número.
        Se houver, ele aparece logo depois do código.
      </p>
      <Button type="submit" disabled={!valido || aguardando} loading={valido && aguardando}>
        Continuar
      </Button>
    </form>
  )
}
