import { useState } from 'react'
import { Confirmacao } from '@/components/ui/Confirmacao'
import { useToast } from '@/components/ui/toastContext'
import { formatPhone } from '@/utils/formatPhone'
import { useEnviarLinkDosDocumentos } from '@/hooks/useConsents'
import { dataDe, horaDe, mensagemDoErro } from '@/utils/pagamento'

interface EnviarLinkDosDocumentosProps {
  appointmentId: string
  /** Quando a recepção já mandou o link para esta sessão; null se nunca. */
  linkEnviadoEm: string | null
  /** Para a confirmação dizer para quem (PRD 053). */
  telefone?: string | null
}

/**
 * Link dos documentos (termo e ficha) pelo WhatsApp, para a paciente
 * preencher e assinar pelo celular antes da sessão (PRD 048).
 *
 * Nada sai no primeiro clique (PRD 053): a confirmação inline diz para quem e
 * quando foi o último envio.
 *
 * Dois desvios do caminho feliz, na própria linha, sem modal:
 * - o WhatsApp falhou: o link existe (é fixo por clínica), então aparece para copiar;
 * - regra do servidor (sessão passada, já assinado, clínica sem domínio): toast
 *   com a mensagem do backend.
 */
export function EnviarLinkDosDocumentos({
  appointmentId,
  linkEnviadoEm,
  telefone = null,
}: EnviarLinkDosDocumentosProps) {
  const enviar = useEnviarLinkDosDocumentos()
  const { showToast } = useToast()
  const [confirmando, setConfirmando] = useState(false)
  const [linkParaCopiar, setLinkParaCopiar] = useState<string | null>(null)
  const [enviadoEm, setEnviadoEm] = useState<string | null>(linkEnviadoEm)

  function mandar() {
    enviar.mutate(appointmentId, {
      onSuccess: (r) => {
        if (r.sent) {
          setLinkParaCopiar(null)
          setEnviadoEm(r.consent_link_sent_at)
          showToast({ message: 'Link dos documentos enviado pelo WhatsApp' })
        } else {
          setLinkParaCopiar(r.link)
        }
      },
      onError: (erro) =>
        showToast({
          message: mensagemDoErro(erro, 'Não foi possível enviar o link.'),
          variant: 'error',
        }),
    })
  }

  async function copiar(link: string) {
    try {
      await navigator.clipboard.writeText(link)
      showToast({ message: 'Link copiado' })
    } catch {
      showToast({ message: 'Não deu para copiar. Selecione o link e copie.', variant: 'error' })
    }
  }

  if (linkParaCopiar) {
    return (
      <div className="mt-1 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        <p>O WhatsApp não enviou. Copie o link e mande para a paciente.</p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            value={linkParaCopiar}
            aria-label="Link dos documentos"
            onFocus={(e) => e.currentTarget.select()}
            className="min-w-0 flex-1 rounded-md border border-amber-200 bg-white px-2 py-1 text-xs text-gray-700"
          />
          <button
            type="button"
            onClick={() => void copiar(linkParaCopiar)}
            className="rounded-md bg-amber-600 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-700 cursor-pointer"
          >
            Copiar
          </button>
        </div>
      </div>
    )
  }

  if (confirmando) {
    return (
      <Confirmacao
        pergunta={`${enviadoEm ? 'Reenviar' : 'Mandar'} o link do termo e da ficha${telefone ? ` para ${formatPhone(telefone)}` : ' para a paciente'} pelo WhatsApp?`}
        detalhe={enviadoEm ? `Último envio em ${dataDe(enviadoEm)} às ${horaDe(enviadoEm)}.` : undefined}
        acao="Enviar"
        loading={enviar.isPending}
        onConfirmar={() => { setConfirmando(false); mandar() }}
        onVoltar={() => setConfirmando(false)}
      />
    )
  }

  return (
    <div className="pt-1">
      <button
        type="button"
        onClick={() => setConfirmando(true)}
        disabled={enviar.isPending}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-60 cursor-pointer"
      >
        {enviar.isPending
          ? 'Enviando…'
          : enviadoEm
            ? 'Reenviar link dos documentos'
            : 'Enviar link dos documentos'}
      </button>
      {enviadoEm && (
        <p className="mt-1 text-xs text-gray-500">
          Link enviado em {dataDe(enviadoEm)} às {horaDe(enviadoEm)}
        </p>
      )}
    </div>
  )
}
