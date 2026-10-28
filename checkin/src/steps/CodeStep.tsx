import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useConfirmCode, useSendCode } from '@/hooks/useCheckin'
import { formatPhone } from '@/utils/format'
import { cx } from '@/utils/cx'

const LENGTH = 6

export function CodeStep({
  clinicId,
  phone,
  devCode,
  onVerified,
  onChangePhone,
}: {
  clinicId: string
  phone: string
  devCode: string | null
  onVerified: (token: string) => void
  onChangePhone: () => void
}) {
  const [code, setCode] = useState('')
  const confirm = useConfirmCode(clinicId)
  const resend = useSendCode(clinicId)
  const shownDevCode = resend.data ?? devCode

  function change(next: string) {
    setCode(next)
    confirm.reset()
    // O sexto dígito já confirma: um toque a menos no balcão.
    if (next.length === LENGTH) {
      confirm.mutate({ phone, code: next }, { onSuccess: onVerified, onError: () => setCode('') })
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Digite o código">
        Enviamos para o WhatsApp {formatPhone(phone.slice(2))}.
      </StepHeader>
      {shownDevCode ? (
        // Só em dev, com o WhatsApp da clínica de teste fora do ar.
        <p className="rounded-2xl border border-accent-200 bg-accent-50 px-5 py-3 text-center text-base text-accent-700">
          Ambiente de teste, sem WhatsApp. Seu código é{' '}
          <strong className="font-bold tabular-nums">{shownDevCode}</strong>.
        </p>
      ) : null}
      <div className="flex justify-center gap-2" aria-label="Código digitado">
        {Array.from({ length: LENGTH }).map((_, i) => (
          <span
            key={i}
            className={cx(
              'flex h-16 w-12 items-center justify-center rounded-xl border-2 bg-surface font-display text-3xl font-semibold text-ink-900',
              i === code.length ? 'border-accent-400' : 'border-ink-200'
            )}
          >
            {code[i] ?? ''}
          </span>
        ))}
      </div>
      <Keypad value={code} maxLength={LENGTH} onChange={change} disabled={confirm.isPending} />
      {confirm.isError ? <ErrorMessage>{confirm.error.message}</ErrorMessage> : null}
      {resend.isError ? <ErrorMessage>{resend.error.message}</ErrorMessage> : null}
      <div className="mx-auto flex w-full max-w-sm flex-col gap-2">
        <Button variant="secondary" loading={resend.isPending} onClick={() => resend.mutate(phone)}>
          {resend.isSuccess ? 'Código reenviado' : 'Reenviar código'}
        </Button>
        <Button variant="ghost" onClick={onChangePhone}>
          Trocar número
        </Button>
      </div>
    </div>
  )
}
