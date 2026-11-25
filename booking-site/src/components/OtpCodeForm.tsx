import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { useConfirmOtp, useSendOtp } from '@/hooks/useBooking'
import type { PacienteVerificado } from '@/types'
import { ESPERA_REENVIO_MS, registraEnvioDeCodigo, segundosAteReenviar } from '@/utils/enviosDeCodigo'

interface OtpCodeFormProps {
  clinicId: string
  /** O celular como a API recebe (ou como foi digitado; `useSendOtp` manda o que vier). */
  phone: string
  /** Como mostrar o celular; sem isto, mostra `phone` como está. */
  phoneLabel?: string
  /** `paciente` (PRD 061): quem é o dono do número, só depois do código. */
  onVerified: (token: string, paciente: PacienteVerificado) => void
}

/** Formulário de código de verificação: envia ao montar (se não enviou há pouco) e permite reenvio com espera. */
export function OtpCodeForm({ clinicId, phone, phoneLabel, onVerified }: OtpCodeFormProps) {
  const [code, setCode] = useState('')
  const sendOtp = useSendOtp(clinicId)
  const confirmOtp = useConfirmOtp(clinicId)
  const [restantes, setRestantes] = useState(() => segundosAteReenviar(clinicId, phone))

  function envia() {
    registraEnvioDeCodigo(clinicId, phone)
    setRestantes(ESPERA_REENVIO_MS / 1000)
    sendOtp.mutate(phone)
  }

  useEffect(() => {
    if (!phone) return
    // Um código saiu há pouco para este celular (ex.: o formulário remontou):
    // não manda outro, só mostra a espera do reenvio.
    if (segundosAteReenviar(clinicId, phone) > 0) return
    // Adiado um tique: o StrictMode monta, desmonta e remonta em dev; disparar
    // a mutação na primeira passada a deixa sem observador ("Enviando..." para
    // sempre). Com a limpeza, só a passada que sobrevive envia.
    const id = window.setTimeout(() => {
      setCode('')
      envia()
    }, 0)
    return () => window.clearTimeout(id)
    // Dispara só quando o celular muda (montagem inclusa), não a cada re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinicId, phone])

  // Contagem do "Reenviar código".
  useEffect(() => {
    if (restantes === 0) return
    const id = window.setInterval(() => setRestantes(segundosAteReenviar(clinicId, phone)), 1000)
    return () => window.clearInterval(id)
  }, [restantes, clinicId, phone])

  function handleConfirm(e: FormEvent) {
    e.preventDefault()
    confirmOtp.mutate({ phone, code }, { onSuccess: (r) => onVerified(r.token, r.paciente ?? null) })
  }

  const podeReenviar = restantes === 0 && !sendOtp.isPending

  return (
    <div>
      <p className="mb-4 text-sm text-ink-600">
        Enviamos um código de confirmação por WhatsApp para{' '}
        <span className="font-medium text-ink-900">{phoneLabel ?? phone}</span>.
      </p>
      <form onSubmit={handleConfirm} className="flex flex-col gap-4">
        <Input
          label="Código de verificação"
          inputMode="numeric"
          maxLength={6}
          placeholder="000000"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          error={confirmOtp.isError ? (confirmOtp.error as Error).message : undefined}
        />
        <Button type="submit" loading={confirmOtp.isPending} disabled={code.length !== 6}>
          Confirmar
        </Button>
        <button
          type="button"
          onClick={envia}
          disabled={!podeReenviar}
          className="text-sm font-medium text-accent-700 underline underline-offset-2 disabled:opacity-50"
        >
          {sendOtp.isPending
            ? 'Enviando...'
            : restantes > 0
              ? `Reenviar código em ${restantes}s`
              : 'Reenviar código'}
        </button>
        {sendOtp.isError ? (
          <p className="text-sm text-danger-500">{(sendOtp.error as Error).message}</p>
        ) : null}
      </form>
    </div>
  )
}
