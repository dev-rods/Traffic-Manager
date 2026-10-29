import { useId, useState } from 'react'
import { useToast } from '@/components/ui/toastContext'
import { useEnviarLink } from '@/hooks/useCaixa'
import { codigoDoErro, mensagemDoErro } from '@/utils/pagamento'

interface EnviarLinkDePagamentoProps {
  appointmentId: string
  /** Já há link pendente: o botão reenvia o mesmo, sem nova cobrança. */
  linkPendente: boolean
  /** Linha do Caixa: botão menor, alinhado à direita. */
  compacto?: boolean
}

function soDigitos(valor: string): string {
  return valor.replace(/\D/g, '').slice(0, 11)
}

function mascaraCpf(digitos: string): string {
  return digitos
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2')
}

/**
 * Link de cobrança pelo WhatsApp para quem não pagou no check-in (PRD 029).
 *
 * Três desvios do caminho feliz, todos na própria linha, sem modal:
 * - sem CPF conhecido, o backend responde `CPF_REQUIRED` e aparece o campo;
 * - o WhatsApp falhou: a cobrança existe, então o link aparece para copiar;
 * - erro do Asaas ou da regra (já pago): toast com a mensagem do backend.
 */
export function EnviarLinkDePagamento({
  appointmentId,
  linkPendente,
  compacto = false,
}: EnviarLinkDePagamentoProps) {
  const enviar = useEnviarLink()
  const { showToast } = useToast()
  const [pedindoCpf, setPedindoCpf] = useState(false)
  const [cpf, setCpf] = useState('')
  const [linkParaCopiar, setLinkParaCopiar] = useState<string | null>(null)
  const campoId = useId()

  function mandar(comCpf?: string) {
    enviar.mutate(
      { appointmentId, cpf: comCpf },
      {
        onSuccess: (r) => {
          setPedindoCpf(false)
          if (r.sent) {
            setLinkParaCopiar(null)
            showToast({ message: 'Link de pagamento enviado pelo WhatsApp' })
          } else {
            setLinkParaCopiar(r.invoiceUrl)
          }
        },
        onError: (erro) => {
          if (codigoDoErro(erro) === 'CPF_REQUIRED') {
            setPedindoCpf(true)
            return
          }
          showToast({
            message: mensagemDoErro(erro, 'Não foi possível enviar o link.'),
            variant: 'error',
          })
        },
      }
    )
  }

  async function copiar(link: string) {
    try {
      await navigator.clipboard.writeText(link)
      showToast({ message: 'Link copiado' })
    } catch {
      showToast({ message: 'Não deu para copiar. Selecione o link e copie.', variant: 'error' })
    }
  }

  const rotulo = linkPendente ? 'Reenviar link pelo WhatsApp' : 'Enviar link pelo WhatsApp'

  if (linkParaCopiar) {
    return (
      <div className="mt-1 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        <p>O WhatsApp não enviou. A cobrança foi criada: copie o link e mande para a paciente.</p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            value={linkParaCopiar}
            aria-label="Link de pagamento"
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

  if (pedindoCpf) {
    const valido = cpf.length === 11
    return (
      <form
        className="mt-1 space-y-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (valido) mandar(cpf)
        }}
      >
        <label htmlFor={campoId} className="block text-xs text-gray-500">
          CPF de quem vai pagar (o Asaas exige)
        </label>
        <div className="flex gap-2">
          <input
            id={campoId}
            inputMode="numeric"
            autoComplete="off"
            autoFocus
            value={mascaraCpf(cpf)}
            onChange={(e) => setCpf(soDigitos(e.target.value))}
            placeholder="000.000.000-00"
            className="min-w-0 flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm tabular-nums focus:border-emerald-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!valido || enviar.isPending}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60 cursor-pointer"
          >
            {enviar.isPending ? 'Enviando…' : 'Enviar'}
          </button>
          <button
            type="button"
            onClick={() => setPedindoCpf(false)}
            className="rounded-md px-2 py-1.5 text-sm text-gray-500 hover:bg-gray-100 cursor-pointer"
          >
            Voltar
          </button>
        </div>
      </form>
    )
  }

  return (
    <button
      type="button"
      onClick={() => mandar()}
      disabled={enviar.isPending}
      className={
        compacto
          ? 'rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 cursor-pointer'
          : 'mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 cursor-pointer'
      }
    >
      {enviar.isPending ? 'Enviando…' : rotulo}
    </button>
  )
}
