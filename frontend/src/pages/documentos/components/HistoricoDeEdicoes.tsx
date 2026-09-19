import { useSessionRecordHistory } from '@/hooks/useSessionRecords'
import { formatarData } from '@/lib/prontuario'

interface HistoricoDeEdicoesProps {
  recordId: string
}

const ACAO = {
  CREATE: 'criou',
  UPDATE: 'alterou',
  DELETE: 'excluiu',
} as const

/**
 * O que o selo "editado" abre.
 *
 * O André escolheu "edita, e o anterior fica guardado" (17/09/2026). A trilha
 * guarda o estado completo a cada escrita, e é isso que permite reconstituir o
 * que foi escrito e quando — sem transformar cada correção de digitação numa
 * retificação formal.
 */
export function HistoricoDeEdicoes({ recordId }: HistoricoDeEdicoesProps) {
  const { data, isLoading, isError, refetch } = useSessionRecordHistory(recordId)

  if (isLoading) {
    return <p className="px-3 py-2 text-xs text-gray-400">Carregando histórico…</p>
  }

  if (isError) {
    return (
      <div className="px-3 py-2 text-xs text-gray-500">
        Não foi possível carregar o histórico.{' '}
        <button type="button" onClick={() => refetch()} className="text-brand-600 underline">
          Tentar de novo
        </button>
      </div>
    )
  }

  const edicoes = data?.history ?? []
  if (edicoes.length === 0) {
    return <p className="px-3 py-2 text-xs text-gray-400">Sem alterações registradas.</p>
  }

  return (
    <ol className="space-y-2 px-3 py-2">
      {edicoes.map((e) => (
        <li key={e.id} className="text-xs text-gray-600">
          <span className="text-gray-400">
            {formatarData(e.changed_at)} · {e.changed_by_name ?? 'não identificado'}
          </span>{' '}
          <span className="font-medium text-gray-700">{ACAO[e.action]}</span>
          {e.snapshot?.applications?.length ? (
            <ul className="mt-0.5 pl-3 text-gray-500">
              {e.snapshot.applications.map((a, i) => (
                <li key={i}>
                  {a.area_name}
                  {a.fluence_j ? ` — ${a.fluence_j} J` : ''}
                  {a.energy_kj ? ` · ${a.energy_kj} kJ` : ''}
                  {a.stacks ? ` · ${a.stacks} stacks` : ''}
                  {a.passes ? ` · ${a.passes} passadas` : ''}
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ol>
  )
}
