import { useState } from 'react'
import type {
  AplicacaoDeSessao,
  MetodoLaser,
  ParametroDoProtocolo,
  ClinicArea,
  SkinType,
} from '@/types'
import {
  ROTULO_DO_METODO,
  hrDesaconselhado,
  metodosDaArea,
  sugestao,
} from '@/lib/protocolo'
import { ParametrosDoMetodo } from './ParametrosDoMetodo'

interface AplicacoesFieldProps {
  aplicacoes: AplicacaoDeSessao[]
  onChange: (aplicacoes: AplicacaoDeSessao[]) => void
  parametros: ParametroDoProtocolo[]
  areas: ClinicArea[]
  /** area_id -> protocol_area_key, vindo do backend. */
  mapaDeAreas: Map<string, string>
  skinType: SkinType | null
  bronzeada: boolean
  disabled?: boolean
}

/**
 * A tabela de aplicações: uma linha por área, com método e parâmetros.
 *
 * Nasce pré-preenchida do agendamento, e tudo é editável — adicionar área,
 * remover e alterar parâmetro (decisão do André em 17/09/2026). O caso comum é
 * a profissional conferir e salvar.
 *
 * Área sem ligação no protocolo mostra "sem parâmetro sugerido" em vez de campo
 * vazio mudo: ela precisa saber que o silêncio é do protocolo, não da tela.
 */
export function AplicacoesField({
  aplicacoes,
  onChange,
  parametros,
  areas,
  mapaDeAreas,
  skinType,
  bronzeada,
  disabled,
}: AplicacoesFieldProps) {
  const [novaArea, setNovaArea] = useState('')

  const altera = (indice: number, mudanca: Partial<AplicacaoDeSessao>) => {
    onChange(aplicacoes.map((a, i) => (i === indice ? { ...a, ...mudanca } : a)))
  }

  /** Trocar o método repõe a sugestão e limpa o que o método novo não usa. */
  const trocaMetodo = (indice: number, metodo: MetodoLaser | null) => {
    const atual = aplicacoes[indice]
    const nova = sugestao(parametros, atual.protocol_area_key, metodo, skinType)
    altera(indice, {
      method: metodo,
      fluence_j: nova?.fluence_j ?? null,
      energy_kj: nova?.energy_kj ?? null,
      stacks: nova?.stacks ?? null,
      passes: nova?.passes ?? null,
    })
  }

  const adiciona = (nome: string, areaId: string | null, chave: string | null) => {
    const metodos = metodosDaArea(parametros, chave)
    const metodo = metodos.length === 1 ? metodos[0] : null
    const nova = sugestao(parametros, chave, metodo, skinType)
    onChange([
      ...aplicacoes,
      {
        area_id: areaId,
        area_name: nome,
        protocol_area_key: chave,
        method: metodo,
        fluence_j: nova?.fluence_j ?? null,
        energy_kj: nova?.energy_kj ?? null,
        stacks: nova?.stacks ?? null,
        passes: nova?.passes ?? null,
        display_order: aplicacoes.length,
      },
    ])
    setNovaArea('')
  }

  const sugeridas = areas
    .filter(() => novaArea.length >= 2)
    .filter((a) => a.name.toLowerCase().includes(novaArea.toLowerCase()))
    .slice(0, 6)

  return (
    <div>
      <span className="mb-1.5 block text-xs font-medium text-gray-500">Aplicações</span>

      {aplicacoes.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-center text-xs text-gray-400">
          Nenhuma área ainda. Adicione abaixo o que foi aplicado nesta sessão.
        </p>
      ) : (
        <ul className="space-y-3">
          {aplicacoes.map((ap, i) => {
            const metodos = metodosDaArea(parametros, ap.protocol_area_key)
            const semProtocolo = metodos.length === 0
            return (
              <li key={`${ap.area_name}-${i}`} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-medium text-gray-800">{ap.area_name}</span>
                  <button
                    type="button"
                    onClick={() => onChange(aplicacoes.filter((_, j) => j !== i))}
                    disabled={disabled}
                    className="text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
                    aria-label={`Remover ${ap.area_name}`}
                  >
                    Remover
                  </button>
                </div>

                {semProtocolo ? (
                  <p className="mt-1.5 text-xs text-gray-400">
                    Sem parâmetro sugerido — o protocolo não tem esta área. Anote
                    o que usou nas observações.
                  </p>
                ) : (
                  <div className="mt-2 flex flex-wrap items-end gap-4">
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-gray-500">Método</span>
                      <select
                        value={ap.method ?? ''}
                        disabled={disabled}
                        onChange={(e) =>
                          trocaMetodo(i, (e.target.value || null) as MetodoLaser | null)
                        }
                        className="rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                      >
                        <option value="">Escolher…</option>
                        {metodos.map((m) => (
                          <option
                            key={m}
                            value={m}
                            disabled={m === 'HR' && hrDesaconselhado(bronzeada)}
                          >
                            {ROTULO_DO_METODO[m]}
                            {m === 'HR' && hrDesaconselhado(bronzeada)
                              ? ' — não usar em pele bronzeada'
                              : ''}
                          </option>
                        ))}
                      </select>
                    </label>

                    <ParametrosDoMetodo
                      aplicacao={ap}
                      onChange={(campo, valor) => altera(i, { [campo]: valor })}
                      disabled={disabled}
                    />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <div className="relative mt-3">
        <input
          type="text"
          value={novaArea}
          disabled={disabled}
          placeholder="+ Adicionar área"
          onChange={(e) => setNovaArea(e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
        />
        {novaArea.length >= 2 && (
          <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
            {sugeridas.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => adiciona(a.name, a.id, mapaDeAreas.get(a.id) ?? null)}
                  className="block w-full px-3 py-2 text-left text-sm text-gray-800 hover:bg-gray-50"
                >
                  {a.name}
                </button>
              </li>
            ))}
            {/* Área fora do catálogo é caso legítimo, não erro. */}
            <li className="border-t border-gray-100">
              <button
                type="button"
                onClick={() => adiciona(novaArea, null, null)}
                className="block w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-50"
              >
                Usar &quot;{novaArea}&quot; como texto livre
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  )
}
