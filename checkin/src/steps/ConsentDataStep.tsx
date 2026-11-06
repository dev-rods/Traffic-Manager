import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import type { CheckinAppointment, ConsentPrefill, ConsentStartPayload } from '@/types'
import { cx } from '@/utils/cx'
import {
  digitsToIsoDate,
  formatCpf,
  formatDateDigits,
  formatPhone,
  isMinorAt,
  isValidCpf,
  isValidEmail,
  isValidMobile,
  isoDateToDigits,
  onlyDigits,
  toApiPhone,
} from '@/utils/format'

interface ConsentDataStepProps {
  appointment: CheckinAppointment
  // Os dados conferidos seguem para a ficha de anamnese e só então para o
  // backend (PRD 038): esta tela não chama a API.
  onContinue: (payload: ConsentStartPayload) => void
  onRestart: () => void
}

interface Person {
  name: string
  cpf: string
  birth: string
  email: string
  phone: string
}

function fromPrefill(p: ConsentPrefill | null): Person {
  return {
    name: p?.name ?? '',
    cpf: '',
    birth: isoDateToDigits(p?.birthDate ?? null),
    email: p?.email ?? '',
    phone: '',
  }
}

function guardianFromPrefill(p: ConsentPrefill | null): Person {
  const g = p?.guardian
  return {
    name: g?.name ?? '',
    cpf: '',
    birth: isoDateToDigits(g?.birthDate ?? null),
    email: g?.email ?? '',
    phone: g?.phone ? onlyDigits(g.phone).replace(/^55/, '') : '',
  }
}

function hasTwoNames(name: string): boolean {
  return name.trim().split(/\s+/).length >= 2
}

/**
 * Primeira tela do termo (PRD 036): a paciente confere ou completa os dados
 * que vão impressos no documento e diz se autoriza o uso de imagem. Menor de
 * idade na data da sessão informa o responsável legal, que é quem assina.
 * Não há "pular": sem termo, só a recepção libera (dispensa pelo painel).
 */
export function ConsentDataStep({ appointment, onContinue, onRestart }: ConsentDataStepProps) {
  const prefill = appointment.consentPrefill
  const [patient, setPatient] = useState<Person>(() => fromPrefill(prefill))
  const [guardian, setGuardian] = useState<Person>(() => guardianFromPrefill(prefill))
  const [useKnownCpf, setUseKnownCpf] = useState(prefill?.cpfKnown ?? false)
  const [image, setImage] = useState<boolean | null>(null)
  const [touched, setTouched] = useState(false)

  if (!prefill || !prefill.clinicReady) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        <StepHeader title="Termo de consentimento">
          A clínica ainda não configurou o termo. Chame a recepção, por favor.
        </StepHeader>
        <Button variant="secondary" onClick={onRestart} className="w-full max-w-sm">
          Voltar ao início
        </Button>
      </div>
    )
  }

  const birthIso = digitsToIsoDate(patient.birth)
  const minor = birthIso ? isMinorAt(birthIso, appointment.date) : prefill.isMinor
  const guardianBirthIso = digitsToIsoDate(guardian.birth)

  const errors = {
    name: !hasTwoNames(patient.name) ? 'Informe o nome completo.' : null,
    cpf:
      !useKnownCpf && !isValidCpf(patient.cpf)
        ? patient.cpf.length === 11
          ? 'Confira o CPF: os números não batem.'
          : 'Informe o CPF.'
        : null,
    birth: !birthIso ? 'Informe a data de nascimento.' : null,
    email: !isValidEmail(patient.email) ? 'Informe um e-mail válido.' : null,
    image: image === null ? 'Escolha uma das opções.' : null,
    guardianName: minor && !hasTwoNames(guardian.name) ? 'Informe o nome completo.' : null,
    guardianCpf:
      minor && !isValidCpf(guardian.cpf)
        ? guardian.cpf.length === 11
          ? 'Confira o CPF: os números não batem.'
          : 'Informe o CPF.'
        : null,
    guardianBirth: minor && !guardianBirthIso ? 'Informe a data de nascimento.' : null,
    guardianPhone: minor && !isValidMobile(guardian.phone) ? 'Informe o celular com DDD.' : null,
    guardianEmail: minor && !isValidEmail(guardian.email) ? 'Informe um e-mail válido.' : null,
  }
  const valid = Object.values(errors).every((e) => e === null)
  const show = (key: keyof typeof errors) => (touched ? errors[key] : null)

  function submit() {
    setTouched(true)
    if (!valid || !birthIso || image === null) return
    onContinue({
      fullName: patient.name.trim(),
      cpf: useKnownCpf ? null : patient.cpf,
      birthDate: birthIso,
      email: patient.email.trim(),
      imageAuthorized: image,
      guardian:
        minor && guardianBirthIso
          ? {
              name: guardian.name.trim(),
              cpf: guardian.cpf,
              birthDate: guardianBirthIso,
              phone: toApiPhone(guardian.phone),
              email: guardian.email.trim(),
            }
          : null,
    })
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Termo de consentimento">
        Confira seus dados: eles vão impressos no termo que você assina a seguir.
      </StepHeader>

      <div className="flex flex-col gap-5 rounded-3xl bg-surface p-6 shadow-card">
        <TextField
          label="Nome completo"
          value={patient.name}
          onChange={(v) => setPatient({ ...patient, name: v })}
          autoComplete="off"
          autoCapitalize="words"
          error={show('name')}
        />
        {useKnownCpf ? (
          <div className="flex flex-col gap-2">
            <span className="font-display text-lg font-semibold text-ink-800">CPF</span>
            <div className="flex min-h-16 items-center justify-between gap-4 rounded-2xl border-2 border-ink-200 bg-ink-50 px-5">
              <span className="text-xl tabular-nums text-ink-700">{prefill.cpfMasked}</span>
              <button
                type="button"
                onClick={() => setUseKnownCpf(false)}
                className="min-h-12 rounded-xl px-3 font-display text-base font-semibold text-accent-700 active:bg-accent-50"
              >
                Não é meu CPF
              </button>
            </div>
          </div>
        ) : (
          <TextField
            label="CPF"
            value={formatCpf(patient.cpf)}
            onChange={(v) => setPatient({ ...patient, cpf: onlyDigits(v).slice(0, 11) })}
            inputMode="numeric"
            autoComplete="off"
            placeholder="000.000.000-00"
            error={show('cpf')}
          />
        )}
        <TextField
          label="Data de nascimento"
          value={formatDateDigits(patient.birth)}
          onChange={(v) => setPatient({ ...patient, birth: onlyDigits(v).slice(0, 8) })}
          inputMode="numeric"
          autoComplete="off"
          placeholder="dd/mm/aaaa"
          error={show('birth')}
        />
        <TextField
          label="E-mail"
          value={patient.email}
          onChange={(v) => setPatient({ ...patient, email: v })}
          type="email"
          inputMode="email"
          autoComplete="off"
          autoCapitalize="none"
          placeholder="voce@exemplo.com"
          hint="Você recebe a cópia assinada por e-mail."
          error={show('email')}
        />
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-3 font-display text-lg font-semibold text-ink-800">
          Autoriza o uso da sua imagem (fotos antes e depois) para divulgação?
        </legend>
        <div className="grid grid-cols-2 gap-4">
          <Choice selected={image === true} onClick={() => setImage(true)}>
            Autorizo
          </Choice>
          <Choice selected={image === false} onClick={() => setImage(false)}>
            Não autorizo
          </Choice>
        </div>
        {show('image') ? <ErrorMessage>{errors.image}</ErrorMessage> : null}
      </fieldset>

      {minor ? (
        <div className="flex flex-col gap-5 rounded-3xl border-2 border-accent-200 bg-accent-50 p-6">
          <div>
            <h2 className="font-display text-2xl font-bold text-ink-900">Responsável legal</h2>
            <p className="text-base text-ink-600">
              Menor de 18 anos na data da sessão: o responsável assina o termo.
            </p>
          </div>
          <TextField
            label="Nome completo do responsável"
            value={guardian.name}
            onChange={(v) => setGuardian({ ...guardian, name: v })}
            autoComplete="off"
            autoCapitalize="words"
            error={show('guardianName')}
          />
          <TextField
            label="CPF do responsável"
            value={formatCpf(guardian.cpf)}
            onChange={(v) => setGuardian({ ...guardian, cpf: onlyDigits(v).slice(0, 11) })}
            inputMode="numeric"
            autoComplete="off"
            placeholder="000.000.000-00"
            error={show('guardianCpf')}
          />
          <TextField
            label="Nascimento do responsável"
            value={formatDateDigits(guardian.birth)}
            onChange={(v) => setGuardian({ ...guardian, birth: onlyDigits(v).slice(0, 8) })}
            inputMode="numeric"
            autoComplete="off"
            placeholder="dd/mm/aaaa"
            error={show('guardianBirth')}
          />
          <TextField
            label="Celular do responsável"
            value={formatPhone(guardian.phone)}
            onChange={(v) => setGuardian({ ...guardian, phone: onlyDigits(v).slice(0, 11) })}
            inputMode="tel"
            autoComplete="off"
            placeholder="(11) 99999-9999"
            hint="O código de assinatura chega neste WhatsApp."
            error={show('guardianPhone')}
          />
          <TextField
            label="E-mail do responsável"
            value={guardian.email}
            onChange={(v) => setGuardian({ ...guardian, email: v })}
            type="email"
            inputMode="email"
            autoComplete="off"
            autoCapitalize="none"
            placeholder="responsavel@exemplo.com"
            error={show('guardianEmail')}
          />
        </div>
      ) : null}

      <div className="mx-auto flex w-full max-w-sm flex-col gap-2">
        <Button disabled={touched && !valid} onClick={submit}>
          Continuar para a ficha de anamnese
        </Button>
        <p className="text-center text-base text-ink-500">
          Dúvidas sobre o termo? Fale com a recepção antes de assinar.
        </p>
      </div>
    </div>
  )
}

function Choice({
  selected,
  onClick,
  children,
}: {
  selected: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={cx(
        'min-h-20 rounded-3xl border-2 px-5 font-display text-2xl font-bold transition-colors duration-150',
        selected
          ? 'border-success-500 bg-success-100 text-success-600'
          : 'border-ink-200 bg-surface text-ink-800 shadow-card active:bg-accent-50'
      )}
    >
      {children}
    </button>
  )
}
