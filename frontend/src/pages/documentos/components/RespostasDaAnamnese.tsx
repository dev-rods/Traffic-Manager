import { AlertasDaAnamnese } from '@/pages/agenda/components/AlertasDaAnamnese'
import { ANAMNESE_PERGUNTAS, FOTOTIPOS } from '@/utils/anamnesePerguntas'
import type { PatientConsent } from '@/types'

interface RespostasDaAnamneseProps {
  consent: PatientConsent
}

function valor(v: boolean | string | undefined): string {
  if (v === true) return 'Sim'
  if (v === false) return 'Não'
  if (typeof v === 'string' && v.trim()) return v
  return '-'
}

/**
 * As respostas da ficha de anamnese de um documento (PRD 038), por seção, na
 * ordem do PDF, com os alertas no topo. Os textos vêm do catálogo gerado do
 * backend; as respostas, do próprio documento. O fototipo é autodeclarado e
 * não é o tipo de pele do prontuário.
 */
export function RespostasDaAnamnese({ consent }: RespostasDaAnamneseProps) {
  const r = consent.answers
  if (!r) return null
  const secoes: {
    nome: string
    itens: { key: string; texto: string; valor: string; destaque: boolean }[]
  }[] = []
  for (const p of ANAMNESE_PERGUNTAS) {
    if (p.conditionalOf && r[p.conditionalOf] !== true) continue
    const v = r[p.key]
    const texto = p.label ?? p.text
    const item = {
      key: p.key,
      texto,
      valor: p.type === 'FOTOTIPO' ? fototipo(valor(v)) : valor(v),
      destaque: v === true,
    }
    const ultima = secoes[secoes.length - 1]
    if (ultima && ultima.nome === p.section) ultima.itens.push(item)
    else secoes.push({ nome: p.section, itens: [item] })
  }

  return (
    <div className="space-y-4" data-testid="respostas-da-anamnese">
      <AlertasDaAnamnese alertas={consent.alertas} />
      {secoes.map((s) => (
        <section key={s.nome} aria-label={s.nome}>
          <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
            {s.nome}
          </h4>
          <dl className="divide-y divide-gray-100 rounded-lg border border-gray-100">
            {s.itens.map((i) => (
              <div
                key={i.key}
                className="flex items-start justify-between gap-4 px-3 py-1.5 text-sm"
              >
                <dt className="text-gray-600">{i.texto}</dt>
                <dd
                  className={`shrink-0 text-right ${i.destaque ? 'font-semibold text-gray-900' : 'text-gray-800'}`}
                >
                  {i.valor}
                </dd>
              </div>
            ))}
          </dl>
          {s.nome.startsWith('8.') && (
            <p className="mt-1 text-xs text-gray-400">
              Autodeclarado pela paciente. O tipo de pele do prontuário é o escolhido pela
              profissional.
            </p>
          )}
        </section>
      ))}
    </div>
  )
}

function fototipo(v: string): string {
  const o = FOTOTIPOS.find((f) => f.value === v)
  return o ? `${o.value} - ${o.text}` : v
}
