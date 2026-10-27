import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useSalvaTemplate, useTemplate } from '@/hooks/useTemplates'
import { renderizaTemplate } from '@/utils/renderizaTemplate'

interface TemplateFieldProps {
  templateKey: string
  label: string
  /** O texto que vale quando a clinica nao escreveu o seu (default do backend). */
  padrao: string
  help?: string
  /** Dados de exemplo para a pre-visualizacao, chave -> valor. */
  exemplo: Record<string, string>
}

/**
 * Edita um texto de `message_templates` da clinica, com pre-visualizacao.
 *
 * Salva separado do formulario da clinica porque mora em outra tabela e tem
 * o proprio ciclo: criar na primeira vez, atualizar depois. Vazio volta ao
 * default - a tela mostra o default como placeholder para a pessoa saber o
 * que vai sair se nao escrever nada.
 *
 * `editado` e null enquanto a pessoa nao mexeu: o que aparece e o texto gravado.
 * Estado derivado, sem efeito - o lint do React 19 recusa setState em effect.
 */
export function TemplateField({ templateKey, label, padrao, help, exemplo }: TemplateFieldProps) {
  const { data: template, isLoading, isError } = useTemplate(templateKey)
  const salvar = useSalvaTemplate(templateKey)
  const [editado, setEditado] = useState<string | null>(null)
  const [salvo, setSalvo] = useState(false)

  const gravado = template?.content ?? ''
  const texto = editado ?? gravado
  const sujo = editado !== null && editado !== gravado
  const preview = renderizaTemplate(texto.trim() || padrao, exemplo)

  const handleSalvar = () => {
    const content = texto.trim() || padrao
    salvar.mutate({ templateId: template?.id ?? null, content }, {
      onSuccess: () => {
        setEditado(null)
        setSalvo(true)
        setTimeout(() => setSalvo(false), 3000)
      },
    })
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <textarea
        value={texto}
        onChange={(e) => setEditado(e.target.value)}
        rows={4}
        placeholder={isLoading ? 'Carregando...' : padrao}
        disabled={isLoading}
        aria-label={label}
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
      />
      {help && <p className="text-[11px] text-gray-400">{help}</p>}
      {isError && <p className="text-xs text-red-500">Não foi possível carregar o texto atual.</p>}

      <div className="rounded-lg bg-gray-50 p-3">
        <p className="mb-1 text-[11px] uppercase tracking-wide text-gray-400">Pré-visualização</p>
        <p className="whitespace-pre-wrap text-sm text-gray-700" data-testid="preview">{preview}</p>
      </div>

      <div className="flex items-center gap-3">
        <Button size="sm" variant="secondary" onClick={handleSalvar} disabled={!sujo || isLoading} loading={salvar.isPending}>
          Salvar texto
        </Button>
        {salvo && <span className="text-sm font-medium text-green-600">Texto salvo</span>}
        {salvar.isError && <span className="text-sm text-red-500">Erro ao salvar o texto</span>}
      </div>
    </div>
  )
}
