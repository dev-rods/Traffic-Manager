import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useClinicAreas } from '@/hooks/useAreas'
import { useDeleteSessionRecord, useSessionRecords } from '@/hooks/useSessionRecords'
import type { RegistroDeSessao, SkinType } from '@/types'
import { ROTULO_DO_METODO } from '@/lib/protocolo'
import { formatarDataDaSessao, resumoDaAplicacao } from '@/lib/prontuario'
import { HistoricoDeEdicoes } from './HistoricoDeEdicoes'
import { RegistroDeSessaoModal } from './RegistroDeSessaoModal'

interface HistoricoDeSessaoProps {
  patientId: string
  skinType: SkinType | null
  /** Vindo do atalho da agenda: abre o modal ja com esta sessao escolhida. */
  agendamentoInicial?: string | null
}

/**
 * A lista de sessões — a tela que responde "que parâmetro usei da última vez?".
 *
 * O parâmetro aparece SEM precisar abrir nada, de propósito: é a pergunta que
 * justifica o documento existir, e escondê-la atrás de um clique transformaria
 * consulta rápida em navegação.
 */
export function HistoricoDeSessao({
  patientId,
  skinType,
  agendamentoInicial,
}: HistoricoDeSessaoProps) {
  const { data, isLoading, isError, refetch } = useSessionRecords(patientId)
  const { data: areas } = useClinicAreas()
  const excluir = useDeleteSessionRecord()

  const [criando, setCriando] = useState(Boolean(agendamentoInicial))
  const [editando, setEditando] = useState<RegistroDeSessao | null>(null)
  const [trilhaAberta, setTrilhaAberta] = useState<string | null>(null)

  if (isLoading) {
    return (
      <ul className="space-y-4" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <li key={i} className="h-24 animate-pulse rounded-lg bg-gray-100" />
        ))}
      </ul>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-gray-200 px-4 py-8 text-center">
        <p className="text-sm text-gray-600">Não foi possível carregar o histórico.</p>
        <Button variant="secondary" className="mt-3" onClick={() => refetch()}>
          Tentar de novo
        </Button>
      </div>
    )
  }

  const registros = data?.records ?? []
  const semRegistro = data?.appointments_without_record ?? []

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs text-gray-400">
          {registros.length === 0
            ? 'Nenhuma sessão registrada'
            : `${registros.length} ${registros.length === 1 ? 'registro' : 'registros'}`}
        </p>
        <Button onClick={() => setCriando(true)}>+ Novo registro</Button>
      </div>

      {registros.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-200 px-4 py-10 text-center">
          <p className="text-sm text-gray-600">Nenhuma sessão registrada ainda.</p>
          {semRegistro.length > 0 && (
            <>
              <p className="mt-2 text-xs text-gray-500">
                Há {semRegistro.length}{' '}
                {semRegistro.length === 1 ? 'atendimento' : 'atendimentos'} na agenda
                sem registro.
              </p>
              <Button className="mt-4" onClick={() => setCriando(true)}>
                Registrar a sessão
              </Button>
            </>
          )}
        </div>
      ) : (
        <ul className="divide-y divide-gray-100">
          {registros.map((r) => (
            <li key={r.id} className="py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-sm font-medium text-gray-800">
                    {formatarDataDaSessao(r.session_date)}
                  </span>
                  <span className="ml-3 text-xs text-gray-500">
                    {r.professional_name ?? 'profissional não informado'}
                  </span>
                  {r.tanned_skin && (
                    <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-700">
                      pele bronzeada
                    </span>
                  )}
                  {r.edit_count > 0 && (
                    <button
                      type="button"
                      onClick={() => setTrilhaAberta(trilhaAberta === r.id ? null : r.id)}
                      className="ml-2 text-[11px] text-gray-400 underline hover:text-gray-600"
                    >
                      editado
                    </button>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => setEditando(r)}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm('Excluir este registro? Ele sai da lista, mas permanece no histórico de alterações.')) {
                        excluir.mutate(r.id)
                      }
                    }}
                    className="text-xs text-gray-400 hover:text-red-600"
                  >
                    Excluir
                  </button>
                </div>
              </div>

              {r.applications.length > 0 && (
                <dl className="mt-2 space-y-1">
                  {r.applications.map((a, i) => (
                    <div key={i} className="flex flex-wrap gap-x-3 text-sm">
                      <dt className="text-gray-700">{a.area_name}</dt>
                      <dd className="text-gray-500">
                        {a.method ? ROTULO_DO_METODO[a.method] : ''}
                        {a.method && resumoDaAplicacao(a) ? ' · ' : ''}
                        {resumoDaAplicacao(a) || (a.method ? '' : 'sem parâmetro registrado')}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}

              {r.notes && <p className="mt-1.5 text-sm text-gray-600">{r.notes}</p>}

              {trilhaAberta === r.id && (
                <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50">
                  <HistoricoDeEdicoes recordId={r.id} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {(criando || editando) && (
        <RegistroDeSessaoModal
          patientId={patientId}
          skinType={skinType}
          areas={areas ?? []}
          sessoesSemRegistro={semRegistro}
          registro={editando}
          agendamentoInicial={editando ? null : agendamentoInicial}
          onClose={() => {
            setCriando(false)
            setEditando(null)
          }}
        />
      )}
    </div>
  )
}
