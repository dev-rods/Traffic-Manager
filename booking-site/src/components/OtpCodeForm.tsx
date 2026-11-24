import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { useConfirmOtp, useSendOtp } from '@/hooks/useBooking'
import type { PacienteVerificado } from '@/types'

interface OtpCodeFormProps {
  clinicId: string
  /** O celular como a API recebe (ou como foi digitado; `useSendOtp` manda o que vier). */
  phone: string
  /** Como mostrar o celular; sem isto, mostra `phone` como está. */
  phoneLabel?: string
  /** `paciente` (PRD 061): quem é o dono do número, só depois do código. */
  onVerified: (token: string, paciente: PacienteVerificado) => void
}

/** Formulário de código de verificação — envia automaticamente ao montar e permite reenvio. */
export function OtpCodeForm({ clinicId, phone, phoneLabel, onVerified }: OtpCodeFormProps) {
  const [code, setCode] = useState('')
  const sendOtp = useSendOtp(clinicId)
  const confirmOtp = useConfirmOtp(clinicId)
  // Para qual celular o código automático já saiu. O StrictMode do React roda
  // o efeito de montagem duas vezes em desenvolvimento e mandava dois códigos
  // (visto em 24/11); a ref sobrevive à remontagem simulada, o efeito não.
  const enviadoPara = useRef<string | null>(null)

  useEffect(() => {
    if (phone && enviadoPara.current !== phone) {
      enviadoPara.current = phone
      setCode('')
      sendOtp.mutate(phone)
    }
    // Dispara só quando o telefone muda (montagem inclusa) — não a cada re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phone])

  function handleConfirm(e: FormEvent) {
    e.preventDefault()
    confirmOtp.mutate({ phone, code }, { onSuccess: (r) => onVerified(r.token, r.paciente ?? null) })
  }

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
          onClick={() => sendOtp.mutate(phone)}
          disabled={sendOtp.isPending}
          className="text-sm font-medium text-accent-700 underline underline-offset-2 disabled:opacity-50"
        >
          {sendOtp.isPending ? 'Enviando...' : 'Reenviar código'}
        </button>
        {sendOtp.isError ? (
          <p className="text-sm text-danger-500">{(sendOtp.error as Error).message}</p>
        ) : null}
      </form>
    </div>
  )
}
