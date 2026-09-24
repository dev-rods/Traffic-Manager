import { Button } from '@/components/ui/Button'
import { WhatsAppIcon, TrashIcon } from '@/components/ui/Icons'

interface AcoesEmLoteProps {
  quantidade: number
  onLimpar: () => void
  onWhatsApp: () => void
  onExcluir: () => void
}

/**
 * A régua que aparece quando há pacientes selecionados.
 *
 * Ela era posicionada com `left-56` - os 224px da sidebar do desktop. Em
 * celular a sidebar virou drawer e deixou de ocupar lugar, então esse recuo
 * empurrava a régua para FORA de uma tela de 375px: ela renderizava e não
 * aparecia, e a seleção em lote virava um recurso sem saída. Relatado em
 * 23/09/2026.
 *
 * Em celular o conteúdo empilha. Em linha, a contagem mais três botões passam
 * de 500px.
 */
export function AcoesEmLote({ quantidade, onLimpar, onWhatsApp, onExcluir }: AcoesEmLoteProps) {
  if (quantidade === 0) return null

  const plural = quantidade !== 1

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-gray-200 bg-white px-4 py-3 shadow-lg md:left-56 md:px-6 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <p className="text-sm font-medium text-gray-700">
          {quantidade} paciente{plural ? 's' : ''} selecionado{plural ? 's' : ''}
        </p>

        <div className="flex items-center gap-2 md:gap-3">
          {/* Limpar vem primeiro em celular e não divide largura: é o desfazer,
              e não uma das duas ações que a pessoa veio fazer. */}
          {/* `aria-label` no botao, e nao um `sr-only` a mais: com o texto
              visivel de `md` E um texto so-para-leitor, o nome acessivel saia
              duplicado ("Limpar selecao Limpar selecao"). O rotulo unico vale
              para os dois tamanhos. */}
          <Button
            variant="ghost"
            size="sm"
            aria-label="Limpar seleção"
            className="min-h-11 order-first md:order-none md:min-h-0"
            onClick={onLimpar}
          >
            <span className="md:hidden" aria-hidden>&times;</span>
            <span className="hidden md:inline" aria-hidden>Limpar seleção</span>
          </Button>

          {/* `min-h-11` são os 44px de toque do CLAUDE.md. O `size="sm"` dá
              ~28px, que foi desenhado para o mouse. */}
          <Button
            variant="success"
            size="sm"
            className="min-h-11 flex-1 md:min-h-0 md:flex-none"
            onClick={onWhatsApp}
          >
            <WhatsAppIcon className="h-4 w-4" />
            <span className="md:hidden">WhatsApp</span>
            <span className="hidden md:inline">Enviar WhatsApp</span>
          </Button>

          <Button
            variant="danger"
            size="sm"
            className="min-h-11 flex-1 md:min-h-0 md:flex-none"
            onClick={onExcluir}
          >
            <TrashIcon className="h-4 w-4" />
            <span className="md:hidden">Excluir</span>
            <span className="hidden md:inline">Excluir selecionados</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
