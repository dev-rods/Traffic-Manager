import { useConsentsDoPaciente, useAbrirDocumentoDoTermo } from '@/hooks/useConsents'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import type { PatientConsent } from '@/types'

interface TermoDeConsentimentoProps {
  patientId: string
}

const SITUACAO: Record<PatientConsent['status'], { label: string; cor: string }> = {
  SIGNED: { label: 'Assinado', cor: 'bg-emerald-100 text-emerald-700' },
  PAPER: { label: 'Em papel', cor: 'bg-emerald-100 text-emerald-700' },
  SIGNING: { label: 'Assinando', cor: 'bg-amber-100 text-amber-700' },
  CANCELLED: { label: 'Cancelado', cor: 'bg-gray-100 text-gray-600' },
  EXPIRED: { label: 'Expirado', cor: 'bg-gray-100 text-gray-600' },
}

function dataDe(iso: string | null): string {
  if (!iso) return '-'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

/**
 * A aba "Termo de consentimento" da pasta de documentos (PRD 036): todas as
 * versões que a paciente assinou (ou registrou em papel), com o PDF assinado
 * e o zip de auditoria por URL de 5 min. A paciente assina no check-in; aqui
 * não se cria nada.
 */
export function TermoDeConsentimento({ patientId }: TermoDeConsentimentoProps) {
  const { data, isLoading, isError, refetch } = useConsentsDoPaciente(patientId)
  const abrir = useAbrirDocumentoDoTermo()

  if (isLoading) {
    return (
      <div aria-busy="true" className="space-y-2">
        <div className="h-10 animate-pulse rounded bg-gray-100" />
        <div className="h-10 animate-pulse rounded bg-gray-100" />
      </div>
    )
  }
  if (isError || !data) {
    return <ErrorState message="Não foi possível carregar os termos." onRetry={() => refetch()} />
  }
  if (data.consents.length === 0) {
    return (
      <EmptyState
        title="Nenhum termo assinado"
        description={
          data.consent_enabled
            ? 'A paciente assina o termo no check-in do iPad, na próxima sessão.'
            : 'A clínica ainda não tem uma versão do termo configurada.'
        }
      />
    )
  }

  return (
    <div className="space-y-3">
      {data.term_version && (
        <p className="text-xs text-gray-400">Versão vigente: {data.term_version}</p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400">
              <th className="pb-2 font-medium">Versão</th>
              <th className="pb-2 font-medium">Situação</th>
              <th className="pb-2 font-medium">Signatário</th>
              <th className="pb-2 font-medium">Data</th>
              <th className="pb-2 font-medium">Registrado por</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.consents.map((c) => {
              const situacao = SITUACAO[c.status]
              const assinadoEm = c.status === 'PAPER' ? c.paper_signed_at : c.signed_at
              return (
                <tr key={c.id} className="align-top">
                  <td className="py-2.5 pr-3 text-gray-800">
                    {c.term_version}
                    {c.term_version === data.term_version && (
                      <span className="ml-1.5 text-[10px] font-semibold text-gray-400">VIGENTE</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${situacao.cor}`}>
                      {situacao.label.toUpperCase()}
                    </span>
                    {c.test && (
                      <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700" title="Assinado em ambiente de teste, sem valor jurídico">
                        TESTE
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-gray-800">
                    {c.signer_name ?? (c.status === 'PAPER' ? 'Paciente' : '-')}
                    {c.signer_kind === 'GUARDIAN' && (
                      <span className="block text-xs text-gray-400">responsável legal</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-gray-800">{dataDe(assinadoEm ?? c.created_at)}</td>
                  <td className="py-2.5 pr-3 text-gray-600">
                    {c.status === 'PAPER' ? c.paper_registered_by ?? '-' : 'iPad (ClickSign)'}
                  </td>
                  <td className="py-2.5 text-right whitespace-nowrap">
                    <button
                      type="button"
                      disabled={!c.has_pdf || abrir.isPending}
                      onClick={() => abrir.mutate({ consentId: c.id, kind: 'pdf' })}
                      className="text-xs font-semibold text-brand-600 hover:text-brand-700 disabled:text-gray-300 disabled:cursor-not-allowed cursor-pointer"
                    >
                      Abrir PDF
                    </button>
                    <button
                      type="button"
                      disabled={!c.has_zip || abrir.isPending}
                      onClick={() => abrir.mutate({ consentId: c.id, kind: 'zip' })}
                      className="ml-3 text-xs font-semibold text-brand-600 hover:text-brand-700 disabled:text-gray-300 disabled:cursor-not-allowed cursor-pointer"
                    >
                      Baixar zip
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {abrir.isError && (
        <p className="text-xs text-red-500">Não foi possível abrir o documento. Tente de novo.</p>
      )}
    </div>
  )
}
