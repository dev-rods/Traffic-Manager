import { useEffect, useRef } from 'react'
import { Button } from './Button'

interface ConfirmacaoProps {
  /** O que vai acontecer, como pergunta: "Mandar o link ... pelo WhatsApp?" */
  pergunta: string
  /** Uma linha a mais quando a consequência não cabe na pergunta. */
  detalhe?: string
  /** Rótulo do botão que executa: "Enviar", "Registrar", "Marcar falta". */
  acao: string
  tom?: 'neutro' | 'perigo'
  loading?: boolean
  onConfirmar: () => void
  onVoltar: () => void
}

/**
 * Confirmação inline: o botão original dá lugar a este bloco, no mesmo lugar,
 * com o resto da linha ainda visível (PRD 053).
 *
 * Existe porque seis ações do pop-up da agenda falam com a paciente ou mexem
 * em dinheiro e executavam no primeiro clique. Inline, e não modal, porque o
 * pop-up é um cartão flutuante: um modal por cima esconderia o contexto que a
 * pessoa precisa para confirmar. O botão da ação nasce com foco, para o custo
 * de quem já leu ser um Enter; Escape volta.
 */
export function Confirmacao({
  pergunta,
  detalhe,
  acao,
  tom = 'neutro',
  loading = false,
  onConfirmar,
  onVoltar,
}: ConfirmacaoProps) {
  const botao = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    botao.current?.focus()
  }, [])

  return (
    <div
      role="group"
      aria-label={pergunta}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onVoltar()
        }
      }}
      className="mt-1 space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm"
    >
      <p className="text-gray-800">{pergunta}</p>
      {detalhe && <p className="text-xs text-gray-500">{detalhe}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="secondary" onClick={onVoltar} disabled={loading}>
          Voltar
        </Button>
        <Button
          ref={botao}
          type="button"
          size="sm"
          variant={tom === 'perigo' ? 'danger' : 'primary'}
          onClick={onConfirmar}
          loading={loading}
        >
          {acao}
        </Button>
      </div>
    </div>
  )
}
