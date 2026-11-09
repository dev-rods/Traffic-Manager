import { Button } from '@/components/ui/Button'
import type { LinhaDaAlteracao } from '@/lib/alteracaoDeAgendamento'

interface ResumoDaAlteracaoProps {
  /** Quem e quando, para pegar o caso de ter aberto o agendamento errado. */
  paciente: string
  quando: string
  linhas: LinhaDaAlteracao[]
  avisos: string[]
  onVoltar: () => void
  onConfirmar: () => void
  salvando?: boolean
  erro?: string | null
}

/**
 * O que vai mudar, antes de mudar (PRD 043).
 *
 * De → para, e não "tem certeza?": o risco é alterar SEM PERCEBER, e pergunta
 * genérica não mostra o que está errado. O cabeçalho nomeia a paciente porque
 * o erro mais caro é editar o agendamento de outra pessoa.
 */
export function ResumoDaAlteracao({
  paciente,
  quando,
  linhas,
  avisos,
  onVoltar,
  onConfirmar,
  salvando,
  erro,
}: ResumoDaAlteracaoProps) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-gray-800">{paciente}</p>
        <p className="text-xs text-gray-500">{quando}</p>
      </div>

      <dl className="divide-y divide-gray-100 rounded-lg border border-gray-200">
        {linhas.map((l) => (
          <div key={l.rotulo} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2.5">
            <dt className="w-20 flex-shrink-0 text-xs font-medium text-gray-500">{l.rotulo}</dt>
            <dd className="flex flex-wrap items-baseline gap-2 text-sm">
              <span className="text-gray-400 line-through">{l.de}</span>
              <span aria-hidden="true" className="text-gray-300">
                &rarr;
              </span>
              <span className="font-medium text-gray-800">{l.para}</span>
            </dd>
          </div>
        ))}
      </dl>

      {avisos.length > 0 && (
        <ul className="space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          {avisos.map((aviso) => (
            <li key={aviso} className="text-sm text-amber-800">
              {aviso}
            </li>
          ))}
        </ul>
      )}

      {erro && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {erro}
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <Button variant="ghost" onClick={onVoltar} disabled={salvando}>
          Voltar
        </Button>
        <Button onClick={onConfirmar} loading={salvando}>
          Confirmar alteração
        </Button>
      </div>
    </div>
  )
}
