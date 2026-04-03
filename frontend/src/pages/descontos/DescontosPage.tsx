import { useState, useEffect } from 'react'
import { useDiscountRules, useUpsertDiscountRules } from '@/hooks/useDiscountRules'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'

export function DescontosPage() {
  const { data, isLoading, isError, error, refetch } = useDiscountRules()
  const upsert = useUpsertDiscountRules()

  const [isActive, setIsActive] = useState(true)
  const [firstSessionPct, setFirstSessionPct] = useState(0)
  const [t2Min, setT2Min] = useState(2)
  const [t2Max, setT2Max] = useState(4)
  const [t2Pct, setT2Pct] = useState(0)
  const [t3Min, setT3Min] = useState(5)
  const [t3Pct, setT3Pct] = useState(0)
  const [saved, setSaved] = useState(false)

  // Populate form when data loads
  const rules = data?.discount_rules
  useEffect(() => {
    if (!rules) return
    setIsActive(rules.is_active)
    setFirstSessionPct(rules.first_session_discount_pct)
    setT2Min(rules.tier_2_min_areas)
    setT2Max(rules.tier_2_max_areas)
    setT2Pct(rules.tier_2_discount_pct)
    setT3Min(rules.tier_3_min_areas)
    setT3Pct(rules.tier_3_discount_pct)
  }, [rules])

  const handleSave = async () => {
    setSaved(false)
    await upsert.mutateAsync({
      is_active: isActive,
      first_session_discount_pct: firstSessionPct,
      tier_2_min_areas: t2Min,
      tier_2_max_areas: t2Max,
      tier_2_discount_pct: t2Pct,
      tier_3_min_areas: t3Min,
      tier_3_discount_pct: t3Pct,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  if (isLoading) return <div className="p-6"><SkeletonTable rows={6} /></div>
  if (isError && !(error instanceof Error && error.message.includes('404'))) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar regras de desconto.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Descontos</h1>
        <p className="text-sm text-gray-400 mt-1">Configure as regras de desconto progressivo da sua clinica</p>
      </div>

      <div className="space-y-8">
        {/* Active toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-gray-800">Descontos ativos</p>
            <p className="text-xs text-gray-400 mt-0.5">Quando desativado, nenhum desconto sera aplicado</p>
          </div>
          <button
            type="button"
            onClick={() => setIsActive(!isActive)}
            className={[
              'relative w-11 h-6 rounded-full transition-colors duration-200',
              isActive ? 'bg-gray-900' : 'bg-gray-200',
            ].join(' ')}
          >
            <span
              className={[
                'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200',
                isActive ? 'translate-x-5' : 'translate-x-0',
              ].join(' ')}
            />
          </button>
        </div>

        <div className={isActive ? '' : 'opacity-40 pointer-events-none'}>
          {/* First session */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-800">Primeira sessao</h2>
              <p className="text-xs text-gray-400 mt-0.5">Desconto para pacientes na primeira visita</p>
            </div>
            <div className="flex items-center gap-3">
              <NumberInput
                value={firstSessionPct}
                onChange={setFirstSessionPct}
                min={0}
                max={100}
                suffix="%"
              />
              <span className="text-xs text-gray-400">de desconto</span>
            </div>
          </section>

          <hr className="my-8 border-gray-100" />

          {/* Progressive tiers */}
          <section className="space-y-6">
            <div>
              <h2 className="text-sm font-semibold text-gray-800">Descontos progressivos</h2>
              <p className="text-xs text-gray-400 mt-0.5">Desconto baseado na quantidade de areas selecionadas no mesmo dia</p>
            </div>

            {/* Tier 2 */}
            <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-4 space-y-3">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Faixa 2</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Min. areas</label>
                  <NumberInput value={t2Min} onChange={setT2Min} min={1} max={99} />
                </div>
                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Max. areas</label>
                  <NumberInput value={t2Max} onChange={setT2Max} min={1} max={99} />
                </div>
                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Desconto</label>
                  <NumberInput value={t2Pct} onChange={setT2Pct} min={0} max={100} suffix="%" />
                </div>
              </div>
            </div>

            {/* Tier 3 */}
            <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-4 space-y-3">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Faixa 3</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Min. areas</label>
                  <NumberInput value={t3Min} onChange={setT3Min} min={1} max={99} />
                </div>
                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Desconto</label>
                  <NumberInput value={t3Pct} onChange={setT3Pct} min={0} max={100} suffix="%" />
                </div>
              </div>
            </div>
          </section>

          {/* Summary */}
          <div className="mt-8 rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-3">Resumo para o paciente</p>
            <div className="text-sm text-gray-600 space-y-1">
              <p>1 area: valor de tabela</p>
              <p>{t2Min} a {t2Max} areas: <span className="font-semibold text-gray-900">{t2Pct}%</span> de desconto</p>
              <p>{t3Min} ou mais areas: <span className="font-semibold text-gray-900">{t3Pct}%</span> de desconto</p>
              {firstSessionPct > 0 && (
                <p className="pt-2 border-t border-gray-100 mt-2">
                  Primeira sessao: <span className="font-semibold text-gray-900">{firstSessionPct}%</span> de desconto
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={upsert.isPending}
            className={[
              'px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors',
              upsert.isPending
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-gray-900 text-white hover:bg-brand-600',
            ].join(' ')}
          >
            {upsert.isPending ? 'Salvando...' : 'Salvar regras'}
          </button>
          {saved && (
            <span className="text-sm text-green-600 font-medium">Salvo com sucesso</span>
          )}
          {upsert.isError && (
            <span className="text-sm text-red-500">Erro ao salvar</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Inline number input component ──────────────────────────
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
