import { useState } from 'react'
import { useDurationRules, useUpdateDurationRules } from '@/hooks/useDurationRules'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { Button } from '@/components/ui/Button'
import { calculaDuracao, DURACAO_PADRAO } from '@/lib/duracao'
import type { DurationRule } from '@/types'

/** Padrão usado quando a clínica ainda não tem regra cadastrada. */
const PADRAO: Omit<DurationRule, 'clinic_id'> = {
  ...DURACAO_PADRAO,
  is_active: true,
}

/**
 * Configuração da duração da sessão.
 *
 * A duração é a soma das durações cadastradas por área, arredondada para cima
 * ao passo e limitada por piso e teto. Antes havia faixas por quantidade de
 * áreas aqui, que discordavam da soma usada no resto do sistema.
 */
export function DuracaoPage() {
  const { data, isLoading, isError, error, refetch } = useDurationRules()

  if (isLoading)
    return (
      <div className="p-6">
        <SkeletonTable rows={4} />
      </div>
    )

  const errorMsg = error instanceof Error ? error.message : ''
  // 404 é esperado para clínica sem regra cadastrada: mostra o formulário com o
  // padrão em vez de uma tela de erro.
  const isNotFound =
    errorMsg.includes('404') || errorMsg.includes('não encontrad') || errorMsg.includes('not found')
  if (isError && !isNotFound) {
    return (
      <div className="p-6">
        <ErrorState
          message={errorMsg || 'Erro ao carregar as regras de duração.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return <DuracaoForm rules={data?.duration_rules ?? PADRAO} />
}

/**
 * O formulário recebe as regras já carregadas e inicializa o estado direto no
 * useState. Sincronizar via useEffect dispararia render em cascata a cada
 * refetch e sobrescreveria o que o usuário estivesse digitando.
 */
function DuracaoForm({ rules }: { rules: Omit<DurationRule, 'clinic_id'> }) {
  const update = useUpdateDurationRules()

  const [piso, setPiso] = useState(rules.floor_minutes)
  const [teto, setTeto] = useState(rules.ceiling_minutes)
  const [passo, setPasso] = useState(rules.step_minutes)
  const [saved, setSaved] = useState(false)

  // O backend recusa as mesmas combinações, mas avisar aqui evita o usuário
  // descobrir só ao salvar.
  const erro =
    piso > teto
      ? 'A duração mínima não pode ser maior que a máxima.'
      : passo > teto
        ? 'O arredondamento não pode ser maior que a duração máxima.'
        : null

  const handleSave = async () => {
    setSaved(false)
    await update.mutateAsync({
      floor_minutes: piso,
      ceiling_minutes: teto,
      step_minutes: passo,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const regrasAtuais = { floor_minutes: piso, ceiling_minutes: teto, step_minutes: passo }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Duração da sessão</h1>
        <p className="text-sm text-gray-400 mt-1">
          Quanto tempo reservar na agenda, a partir das áreas escolhidas
        </p>
      </div>

      <div className="max-w-2xl space-y-8">
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Limites</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              A duração é a soma das áreas escolhidas, sempre dentro destes limites
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Campo label="Duração mínima">
              <NumberInput value={piso} onChange={setPiso} min={1} max={480} suffix="min" />
            </Campo>
            <Campo label="Duração máxima">
              <NumberInput value={teto} onChange={setTeto} min={1} max={480} suffix="min" />
            </Campo>
          </div>
        </section>

        <hr className="border-gray-100" />

        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Arredondamento</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Toda duração vira um múltiplo deste valor, sempre para cima — reservar a mais
              desperdiça um vão, reservar a menos sobrepõe dois atendimentos
            </p>
          </div>
          <div className="w-40">
            <Campo label="Múltiplos de">
              <NumberInput value={passo} onChange={setPasso} min={1} max={60} suffix="min" />
            </Campo>
          </div>
        </section>

        <hr className="border-gray-100" />

        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-800">Como fica na agenda</h2>
          <p className="text-xs text-gray-400">
            Exemplos a partir da soma das durações cadastradas nas áreas
          </p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            {[8, 24, 42, 90].map((soma) => (
              <Resumo
                key={soma}
                soma={`${soma} min de áreas`}
                minutos={calculaDuracao(soma, regrasAtuais)}
              />
            ))}
          </dl>
        </section>

        {erro && <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">{erro}</p>}

        {update.isError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
            {update.error instanceof Error ? update.error.message : 'Erro ao salvar.'}
          </p>
        )}

        <div className="flex items-center gap-3">
          <Button onClick={handleSave} loading={update.isPending} disabled={!!erro}>
            Salvar
          </Button>
          {saved && <span className="text-xs text-green-600">Salvo</span>}
        </div>
      </div>
    </div>
  )
}

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] text-gray-400">{label}</label>
      {children}
    </div>
  )
}

function Resumo({ soma, minutos }: { soma: string; minutos: number }) {
  return (
    <>
      <dt className="text-gray-400">{soma}</dt>
      <dd className="font-medium text-gray-800">{minutos} min</dd>
    </>
  )
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  suffix,
}: {
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  suffix?: string
}) {
  return (
    <div className="relative">
      <input
        type="number"
        value={value}
        onChange={(e) => {
          const v = parseInt(e.target.value, 10)
          if (!isNaN(v) && v >= min && v <= max) onChange(v)
        }}
        min={min}
        max={max}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
      {suffix && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">
          {suffix}
        </span>
      )}
    </div>
  )
}
