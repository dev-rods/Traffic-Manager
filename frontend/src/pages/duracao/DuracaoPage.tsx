import { useState } from 'react'
import { useDurationRules, useUpdateDurationRules } from '@/hooks/useDurationRules'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { Button } from '@/components/ui/Button'
import type { DurationRule } from '@/types'

/** Padrão usado quando a clínica ainda não tem regra cadastrada. */
const PADRAO: Omit<DurationRule, 'clinic_id'> = {
  base_duration_minutes: 15,
  tier_2_min_areas: 2,
  tier_2_max_areas: 3,
  tier_2_duration_minutes: 20,
  tier_3_min_areas: 4,
  tier_3_max_areas: 6,
  tier_3_duration_minutes: 35,
  tier_4_min_areas: 7,
  tier_4_duration_minutes: 45,
  is_active: true,
}

/**
 * Configuração da duração da sessão por quantidade de áreas.
 *
 * A duração não é a soma das durações cadastradas por área: o laser é aplicado
 * em sequência e o preparo não se repete a cada área, então seis áreas levam
 * 35 minutos e não 60.
 */
export function DuracaoPage() {
  const { data, isLoading, isError, error, refetch } = useDurationRules()

  if (isLoading)
    return (
      <div className="p-6">
        <SkeletonTable rows={5} />
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

  const [base, setBase] = useState(rules.base_duration_minutes)
  const [t2Min, setT2Min] = useState(rules.tier_2_min_areas)
  const [t2Max, setT2Max] = useState(rules.tier_2_max_areas)
  const [t2Dur, setT2Dur] = useState(rules.tier_2_duration_minutes)
  const [t3Min, setT3Min] = useState(rules.tier_3_min_areas)
  const [t3Max, setT3Max] = useState(rules.tier_3_max_areas)
  const [t3Dur, setT3Dur] = useState(rules.tier_3_duration_minutes)
  const [t4Min, setT4Min] = useState(rules.tier_4_min_areas)
  const [t4Dur, setT4Dur] = useState(rules.tier_4_duration_minutes)
  const [saved, setSaved] = useState(false)

  // As faixas precisam subir e não podem se sobrepor: fora de ordem, uma delas
  // fica inalcançável e todo agendamento cai na faixa errada. O backend recusa,
  // mas avisar aqui evita o usuário descobrir só ao salvar.
  const erroFaixas =
    t2Max < t2Min
      ? 'O máximo da faixa 2 não pode ser menor que o mínimo.'
      : t3Max < t3Min
        ? 'O máximo da faixa 3 não pode ser menor que o mínimo.'
        : t3Min <= t2Min
          ? 'A faixa 3 precisa começar depois da faixa 2.'
          : t4Min <= t3Min
            ? 'A faixa 4 precisa começar depois da faixa 3.'
            : t3Min !== t2Max + 1
              ? `Áreas entre ${t2Max + 1} e ${t3Min - 1} ficariam sem faixa própria.`
              : t4Min !== t3Max + 1
                ? `Áreas entre ${t3Max + 1} e ${t4Min - 1} ficariam sem faixa própria.`
                : null

  const handleSave = async () => {
    setSaved(false)
    await update.mutateAsync({
      base_duration_minutes: base,
      tier_2_min_areas: t2Min,
      tier_2_max_areas: t2Max,
      tier_2_duration_minutes: t2Dur,
      tier_3_min_areas: t3Min,
      tier_3_max_areas: t3Max,
      tier_3_duration_minutes: t3Dur,
      tier_4_min_areas: t4Min,
      tier_4_duration_minutes: t4Dur,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Duração da sessão</h1>
        <p className="text-sm text-gray-400 mt-1">
          Quanto tempo reservar na agenda conforme a quantidade de áreas tratadas
        </p>
      </div>

      <div className="max-w-2xl space-y-8">
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Sessão de 1 área</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Também é a duração mínima de qualquer atendimento
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-32">
              <NumberInput value={base} onChange={setBase} min={1} max={480} suffix="min" />
            </div>
          </div>
        </section>

        <hr className="border-gray-100" />

        <section className="space-y-6">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Faixas por quantidade de áreas</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              O tempo de preparo não se repete a cada área, por isso a duração não é a soma
            </p>
          </div>

          <TierCard titulo="Faixa 2">
            <Campo label="De (áreas)">
              <NumberInput value={t2Min} onChange={setT2Min} min={1} max={99} />
            </Campo>
            <Campo label="Até (áreas)">
              <NumberInput value={t2Max} onChange={setT2Max} min={1} max={99} />
            </Campo>
            <Campo label="Duração">
              <NumberInput value={t2Dur} onChange={setT2Dur} min={1} max={480} suffix="min" />
            </Campo>
          </TierCard>

          <TierCard titulo="Faixa 3">
            <Campo label="De (áreas)">
              <NumberInput value={t3Min} onChange={setT3Min} min={1} max={99} />
            </Campo>
            <Campo label="Até (áreas)">
              <NumberInput value={t3Max} onChange={setT3Max} min={1} max={99} />
            </Campo>
            <Campo label="Duração">
              <NumberInput value={t3Dur} onChange={setT3Dur} min={1} max={480} suffix="min" />
            </Campo>
          </TierCard>

          <TierCard titulo="Faixa 4 — sem limite">
            <Campo label="A partir de (áreas)">
              <NumberInput value={t4Min} onChange={setT4Min} min={1} max={99} />
            </Campo>
            <Campo label="Duração">
              <NumberInput value={t4Dur} onChange={setT4Dur} min={1} max={480} suffix="min" />
            </Campo>
          </TierCard>
        </section>

        <hr className="border-gray-100" />

        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-800">Como fica na agenda</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <Resumo areas="1 área" minutos={base} />
            <Resumo areas={`${t2Min} a ${t2Max} áreas`} minutos={t2Dur} />
            <Resumo areas={`${t3Min} a ${t3Max} áreas`} minutos={t3Dur} />
            <Resumo areas={`${t4Min}+ áreas`} minutos={t4Dur} />
          </dl>
        </section>

        {erroFaixas && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">{erroFaixas}</p>
        )}

        {update.isError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
            {update.error instanceof Error ? update.error.message : 'Erro ao salvar.'}
          </p>
        )}

        <div className="flex items-center gap-3">
          <Button onClick={handleSave} loading={update.isPending} disabled={!!erroFaixas}>
            Salvar
          </Button>
          {saved && <span className="text-xs text-green-600">Salvo</span>}
        </div>
      </div>
    </div>
  )
}

function TierCard({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-4 space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-600">{titulo}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{children}</div>
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

function Resumo({ areas, minutos }: { areas: string; minutos: number }) {
  return (
    <>
      <dt className="text-gray-400">{areas}</dt>
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
