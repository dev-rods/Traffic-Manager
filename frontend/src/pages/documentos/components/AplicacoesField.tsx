import { useState } from 'react'
import type {
  AplicacaoDeSessao,
  MetodoLaser,
  ParametroDoProtocolo,
  ClinicArea,
  SkinType,
} from '@/types'
import {
  AREAS_PADRAO,
  ROTULO_DO_METODO,
  TODOS_OS_METODOS,
  hrDesaconselhado,
  metodosDaArea,
  sugestao,
} from '@/lib/protocolo'
import { adicionaMetodo, agrupaPorArea, normaliza, removeArea, removeLinha } from '@/lib/aplicacoes'
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

interface SugestaoDeArea {
  chave: string
  nome: string
  areaId: string | null
  protocolAreaKey: string | null
}

const LIMITE_DE_SUGESTOES = 6

/**
 * As aplicações da sessão: um bloco por área, e dentro dele uma linha por
 * método usado, cada uma com os seus parâmetros (PRD 030). Ex.: Axilas com
 * SHR 8 J · 8 kJ e HR 20 J · 1 kJ na mesma sessão.
 *
 * Nasce pré-preenchida do agendamento, e tudo é editável — adicionar área,
 * adicionar método, remover e alterar parâmetro (decisão do André em
 * 17/09/2026). O caso comum é a profissional conferir e salvar.
 *
 * Área sem ligação no protocolo mostra "sem parâmetro sugerido" em vez de campo
 * vazio mudo: ela precisa saber que o silêncio é do protocolo, não da tela.
 */
export function AplicacoesField({
  aplicacoes: recebidas,
  onChange,
  parametros,
  areas,
  mapaDeAreas,
  skinType,
  bronzeada,
  disabled,
}: AplicacoesFieldProps) {
  const [novaArea, setNovaArea] = useState('')

  // Contígua por área: o índice de cada linha é o mesmo na tela e no que sobe.
  const aplicacoes = normaliza(recebidas)
  const blocos = agrupaPorArea(aplicacoes)

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
    onChange(
      normaliza([
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
    )
    setNovaArea('')
  }

  const busca = novaArea.trim().toLowerCase()
  const nomesDoCatalogo = new Set(areas.map((a) => a.name.toLowerCase()))
  const sugeridas: SugestaoDeArea[] =
    busca.length < 2
      ? []
      : [
          // As padrão primeiro: ela não acha "Interno de Virilha" em lugar
          // nenhum além daqui. Se a clínica tiver área com o mesmo nome, vale
          // a do catálogo.
          ...AREAS_PADRAO.filter(
            (p) =>
              p.nome.toLowerCase().includes(busca) && !nomesDoCatalogo.has(p.nome.toLowerCase())
          ).map((p) => ({
            chave: `padrao:${p.protocol_area_key}`,
            nome: p.nome,
            areaId: null,
            protocolAreaKey: p.protocol_area_key,
          })),
          ...areas
            .filter((a) => a.name.toLowerCase().includes(busca))
            .map((a) => ({
              chave: a.id,
              nome: a.name,
              areaId: a.id,
              protocolAreaKey: mapaDeAreas.get(a.id) ?? null,
            })),
        ].slice(0, LIMITE_DE_SUGESTOES)

  // Onde cada bloco começa na lista plana. Como `aplicacoes` está
  // normalizada, os blocos são contíguos e o índice é a soma corrida.
  const inicios = blocos.map((_, b) =>
    blocos.slice(0, b).reduce((total, anterior) => total + anterior.linhas.length, 0)
  )

  return (
    <div>
      <span className="mb-1.5 block text-xs font-medium text-gray-500">Aplicações</span>

      {blocos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-center text-xs text-gray-400">
          Nenhuma área ainda. Adicione abaixo o que foi aplicado nesta sessão.
        </p>
      ) : (
        <ul className="space-y-3">
          {blocos.map((bloco, b) => {
            // TODOS os métodos, sempre. O protocolo diz qual COMEÇAR, não
            // qual é permitido: decisão do André em 19/09/2026, depois de não
            // conseguir escolher Stacking numa axila (que tem SHR e HR no
            // material). Quem decide conduta é quem aplica.
            const comSugestao = metodosDaArea(parametros, bloco.protocol_area_key)
            const variasLinhas = bloco.linhas.length > 1

            return (
              <li key={bloco.chave} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-medium text-gray-800">{bloco.area_name}</span>
                  <button
                    type="button"
                    onClick={() => onChange(removeArea(aplicacoes, bloco.chave))}
                    disabled={disabled}
                    className="text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
                    aria-label={`Remover ${bloco.area_name}`}
                  >
                    Remover
                  </button>
                </div>

                <ul className="divide-y divide-gray-100">
                  {bloco.linhas.map((ap, l) => {
                    const i = inicios[b] + l
                    const rotuloDaLinha = ap.method ? ROTULO_DO_METODO[ap.method] : 'método'
                    return (
                      <li key={i} className="py-2.5 first:pt-2 last:pb-1">
                        <div className="flex flex-wrap items-end gap-4">
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
                              {TODOS_OS_METODOS.map((m) => (
                                // Nenhuma opção é `disabled`. O aviso da pele
                                // bronzeada aparece no rótulo e em
                                // AvisosDoProtocolo, e para por aí: software
                                // que impede conduta clínica é contornado por
                                // fora, e aí a sessão acontece sem registro.
                                <option key={m} value={m}>
                                  {ROTULO_DO_METODO[m]}
                                  {m === 'HR' && hrDesaconselhado(bronzeada)
                                    ? ' — não indicado em pele bronzeada'
                                    : !comSugestao.includes(m)
                                      ? ' — sem sugestão para esta área'
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

                          {variasLinhas && (
                            <button
                              type="button"
                              onClick={() => onChange(removeLinha(aplicacoes, i))}
                              disabled={disabled}
                              className="ml-auto py-1.5 text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
                              aria-label={`Remover ${rotuloDaLinha} de ${bloco.area_name}`}
                            >
                              Remover método
                            </button>
                          )}
                        </div>

                        {ap.method && !comSugestao.includes(ap.method) && (
                          <p className="mt-1.5 text-xs text-gray-400">
                            O protocolo não traz {ROTULO_DO_METODO[ap.method]} para esta área.
                            Informe os parâmetros que você usou.
                          </p>
                        )}
                      </li>
                    )
                  })}
                </ul>

                <button
                  type="button"
                  onClick={() =>
                    onChange(adicionaMetodo(aplicacoes, bloco.chave, parametros, skinType))
                  }
                  disabled={disabled}
                  className="-mx-2 mt-1 rounded-lg px-2 py-2.5 text-xs font-medium text-brand-600 hover:bg-brand-50 disabled:opacity-50"
                  aria-label={`Adicionar método em ${bloco.area_name}`}
                >
                  + Adicionar método
                </button>
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
        {busca.length >= 2 && (
          <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
            {sugeridas.map((s) => (
              <li key={s.chave}>
                <button
                  type="button"
                  onClick={() => adiciona(s.nome, s.areaId, s.protocolAreaKey)}
                  className="block w-full px-3 py-2 text-left text-sm text-gray-800 hover:bg-gray-50"
                >
                  {s.nome}
                </button>
              </li>
            ))}
            {/* Área fora do catálogo é caso legítimo, não erro. */}
            <li className="border-t border-gray-100">
              <button
                type="button"
                onClick={() => adiciona(novaArea.trim(), null, null)}
                className="block w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-50"
              >
                Usar &quot;{novaArea.trim()}&quot; como texto livre
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  )
}
