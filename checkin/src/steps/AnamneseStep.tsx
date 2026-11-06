import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { SimNao } from '@/components/ui/SimNao'
import { TextField } from '@/components/ui/TextField'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useSaveAnamnesis } from '@/hooks/useCheckin'
import { ApiError } from '@/services/api'
import type {
  AnamneseCatalogo,
  AnamnesePergunta,
  AnamneseRespostas,
  CheckinAppointment,
  Session,
} from '@/types'
import { cx } from '@/utils/cx'

interface AnamneseStepProps {
  clinicId: string
  session: Session
  appointment: CheckinAppointment
  catalogo: AnamneseCatalogo
  tela: number
  respostas: AnamneseRespostas
  onBack: () => void
  // Chamado depois de o backend gravar a tela; na última, é o fim da ficha.
  onNext: (respostas: AnamneseRespostas) => void
}

const TAMANHO_DO_TEXTO = 300

function habilitada(p: AnamnesePergunta, r: AnamneseRespostas): boolean {
  return p.conditionalOf === null || r[p.conditionalOf] === true
}

/**
 * Valida uma tela do jeito que o backend valida (`anamnese.valida_tela`):
 * Sim/Não obrigatórios, texto obrigatório quando habilitado, fototipo. O
 * backend continua sendo quem decide; aqui é só para o erro aparecer antes
 * da viagem.
 */
function errosDaTela(perguntas: AnamnesePergunta[], r: AnamneseRespostas): Record<string, string> {
  const erros: Record<string, string> = {}
  for (const p of perguntas) {
    if (!habilitada(p, r)) continue
    const v = r[p.key]
    if (p.type === 'SIM_NAO' && typeof v !== 'boolean') erros[p.key] = 'Responda Sim ou Não.'
    if (p.type === 'FOTOTIPO' && !v) erros[p.key] = 'Escolha uma opção.'
    if (p.type === 'TEXTO' && p.required && !String(v ?? '').trim())
      erros[p.key] = 'Preencha este campo.'
  }
  return erros
}

/** Só as chaves desta tela, sem condicionais que deixaram de valer. */
function respostasDaTela(perguntas: AnamnesePergunta[], r: AnamneseRespostas): AnamneseRespostas {
  const saida: AnamneseRespostas = {}
  for (const p of perguntas) {
    if (!habilitada(p, r)) continue
    const v = r[p.key]
    if (v === undefined || v === null) continue
    saida[p.key] = typeof v === 'string' ? v.trim() : v
  }
  return saida
}

/**
 * Uma das 4 telas da ficha de anamnese (PRD 038), dirigida pelo catálogo que
 * o backend manda no bootstrap. Cada "Continuar" grava a tela no backend:
 * queda de rede ou "Recomeçar" não perdem o que já foi respondido. Os
 * textos condicionais só aparecem quando a resposta-mãe é "Sim".
 */
export function AnamneseStep({
  clinicId,
  session,
  appointment,
  catalogo,
  tela,
  respostas,
  onBack,
  onNext,
}: AnamneseStepProps) {
  const save = useSaveAnamnesis(clinicId, session)
  const [local, setLocal] = useState<AnamneseRespostas>(respostas)
  const [touched, setTouched] = useState(false)
  const [campoDoServidor, setCampoDoServidor] = useState<string | null>(null)

  const screen = catalogo.screens.find((s) => s.n === tela)
  if (!screen) return null
  const perguntas = screen.questions
  const erros = errosDaTela(perguntas, local)
  const valida = Object.keys(erros).length === 0
  const ultima = tela === catalogo.screens.length

  function set(key: string, value: boolean | string) {
    setCampoDoServidor(null)
    setLocal((atual) => ({ ...atual, [key]: value }))
  }

  function continuar() {
    setTouched(true)
    if (!valida) return
    const daTela = respostasDaTela(perguntas, local)
    save.mutate(
      { appointmentId: appointment.id, screen: tela, answers: daTela },
      {
        onSuccess: () => onNext({ ...local, ...daTela }),
        onError: (erro) => {
          const campo = erro instanceof ApiError ? erro.field : null
          setCampoDoServidor(campo ?? null)
        },
      }
    )
  }

  const secoes: { nome: string; perguntas: AnamnesePergunta[] }[] = []
  for (const p of perguntas) {
    const ultimaSecao = secoes[secoes.length - 1]
    if (ultimaSecao && ultimaSecao.nome === p.section) ultimaSecao.perguntas.push(p)
    else secoes.push({ nome: p.section, perguntas: [p] })
  }

  return (
    <div className="flex flex-col gap-6">
      <StepHeader title="Ficha de anamnese">
        Tela {tela} de {catalogo.screens.length}. Responda com atenção: as respostas vão impressas
        no documento que você assina.
      </StepHeader>

      {secoes.map((secao) => (
        <section
          key={secao.nome}
          className="flex flex-col gap-5 rounded-3xl bg-surface p-6 shadow-card"
          aria-label={secao.nome}
        >
          <h2 className="font-display text-xl font-bold text-ink-900">{secao.nome}</h2>
          {secao.perguntas.map((p) => {
            if (!habilitada(p, local)) return null
            const erro = touched ? (erros[p.key] ?? null) : null
            const erroServidor = campoDoServidor === p.key ? 'Confira esta resposta.' : null
            if (p.type === 'SIM_NAO') {
              return (
                <SimNao
                  key={p.key}
                  label={p.text}
                  value={typeof local[p.key] === 'boolean' ? (local[p.key] as boolean) : null}
                  onChange={(v) => set(p.key, v)}
                  error={erro ?? erroServidor}
                />
              )
            }
            if (p.type === 'FOTOTIPO') {
              return (
                <Fototipo
                  key={p.key}
                  texto={p.text}
                  opcoes={catalogo.phototypes}
                  value={typeof local[p.key] === 'string' ? (local[p.key] as string) : null}
                  onChange={(v) => set(p.key, v)}
                  error={erro ?? erroServidor}
                />
              )
            }
            return (
              <TextField
                key={p.key}
                id={`anamnese-${p.key}`}
                label={p.label ?? p.text}
                value={typeof local[p.key] === 'string' ? (local[p.key] as string) : ''}
                onChange={(v) => set(p.key, v.slice(0, TAMANHO_DO_TEXTO))}
                autoComplete="off"
                autoCapitalize="sentences"
                placeholder={p.required ? undefined : 'Opcional'}
                error={erro ?? erroServidor}
              />
            )
          })}
        </section>
      ))}

      {save.isError && !campoDoServidor ? <ErrorMessage>{save.error.message}</ErrorMessage> : null}

      <div className="mx-auto flex w-full max-w-md flex-col gap-3">
        <Button loading={save.isPending} disabled={touched && !valida} onClick={continuar}>
          {ultima ? 'Continuar para a assinatura' : 'Continuar'}
        </Button>
        <Button variant="ghost" onClick={onBack} disabled={save.isPending}>
          Voltar
        </Button>
      </div>
    </div>
  )
}

function Fototipo({
  texto,
  opcoes,
  value,
  onChange,
  error,
}: {
  texto: string
  opcoes: { value: string; text: string }[]
  value: string | null
  onChange: (v: string) => void
  error: string | null
}) {
  return (
    <div className="flex flex-col gap-3" role="radiogroup" aria-label={texto}>
      <span className="text-lg leading-snug text-ink-800">{texto}</span>
      <div className="flex flex-col gap-2">
        {opcoes.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            onClick={() => onChange(o.value)}
            className={cx(
              'flex min-h-16 items-center gap-4 rounded-2xl border-2 px-5 text-left text-lg transition-colors duration-150',
              value === o.value
                ? 'border-success-500 bg-success-100 text-success-600'
                : 'border-ink-200 bg-surface text-ink-800 active:bg-accent-50'
            )}
          >
            <span className="font-display text-2xl font-bold">{o.value}</span>
            <span>{o.text}</span>
          </button>
        ))}
      </div>
      {error ? (
        <span role="alert" className="text-base text-danger-500">
          {error}
        </span>
      ) : null}
    </div>
  )
}
