import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useSessionRecords } from '@/hooks/useSessionRecords'
import { HistoricoDeSessao } from './components/HistoricoDeSessao'

/**
 * A pasta de documentos do paciente.
 *
 * Abre DIRETO no histórico, com o seletor de documento no topo: com um tipo de
 * documento, uma tela intermediária cobraria um clique que não decide nada. A
 * pasta existe na estrutura, e o segundo documento entra como aba.
 *
 * O termo de consentimento não aparece como "em breve" — anunciar data que não
 * temos é promessa, e a integração depende de terceiro.
 *
 * O paciente vem na mesma resposta dos registros: não existe GET de paciente
 * no backend, e criar uma Lambda só para o cabeçalho desta tela seria caro para
 * o que ela precisa (nome, telefone e tipo de pele).
 */
export function DocumentosPage() {
  const { patientId } = useParams<{ patientId: string }>()
  // O atalho da agenda chega com ?agendamento=<id> e abre o modal ja com a
  // sessao escolhida: um clique, os parametros, salvar.
  const [searchParams] = useSearchParams()
  const agendamentoInicial = searchParams.get('agendamento')
  const { data, isLoading, isError, refetch } = useSessionRecords(patientId)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl p-4 md:p-6" aria-busy="true">
        <div className="h-8 w-64 animate-pulse rounded bg-gray-100" />
        <div className="mt-6 h-40 animate-pulse rounded-lg bg-gray-100" />
      </div>
    )
  }

  if (isError || !data?.patient || !patientId) {
    return (
      <div className="mx-auto max-w-4xl p-4 md:p-6">
        <p className="text-sm text-gray-600">
          Não foi possível carregar os documentos deste paciente.
        </p>
        <div className="mt-3 flex gap-3">
          <button
            type="button"
            onClick={() => refetch()}
            className="text-sm text-brand-600 underline"
          >
            Tentar de novo
          </button>
          <Link to="/pacientes" className="text-sm text-gray-500 underline">
            Voltar para pacientes
          </Link>
        </div>
      </div>
    )
  }

  const paciente = data.patient

  return (
    <div className="mx-auto max-w-4xl p-4 md:p-6">
      <Link to="/pacientes" className="text-xs text-gray-400 hover:text-gray-600">
        ← Pacientes
      </Link>

      <header className="mt-2">
        <h1 className="text-2xl font-semibold text-gray-900">
          {paciente.name ?? 'Sem nome'}
        </h1>
        <p className="mt-0.5 text-sm text-gray-500">
          {paciente.phone}
          {paciente.skin_type ? (
            <span className="ml-2 text-gray-400">
              · pele {paciente.skin_type === 'BRANCA' ? 'branca' : 'negra'}
            </span>
          ) : (
            <span className="ml-2 text-amber-600">
              · tipo de pele não marcado
            </span>
          )}
        </p>
      </header>

      <nav className="mt-6 border-b border-gray-200" aria-label="Documentos">
        <span className="inline-block border-b-2 border-brand-500 pb-2 text-sm font-medium text-gray-900">
          Histórico por sessão
        </span>
      </nav>

      <section className="mt-6">
        <HistoricoDeSessao
          patientId={patientId}
          skinType={paciente.skin_type}
          agendamentoInicial={agendamentoInicial}
        />
      </section>
    </div>
  )
}
