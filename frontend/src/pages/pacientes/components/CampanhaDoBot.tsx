const MAX_DATAS = 3

interface CampanhaDoBotProps {
  datasDisponiveis: string[]
  selecionadas: string[]
  onSelecionar: (datas: string[]) => void
  ativa: boolean
  onAtivar: (ativa: boolean) => void
}

function rotulo(iso: string) {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

/**
 * Quem conduz a conversa depois do disparo.
 *
 * O disparo é o começo de um atendimento, não uma mensagem solta: por isso o
 * bot assume por padrão. O que precisa ficar explícito é o contrário - que a
 * atendente pode desligar - e QUAIS datas o bot vai oferecer, porque elas
 * governam a conversa inteira e não necessariamente batem com o texto acima se
 * alguém o editar à mão.
 */
export function CampanhaDoBot({
  datasDisponiveis, selecionadas, onSelecionar, ativa, onAtivar,
}: CampanhaDoBotProps) {
  const alterna = (data: string) => {
    if (selecionadas.includes(data)) {
      onSelecionar(selecionadas.filter((d) => d !== data))
    } else if (selecionadas.length < MAX_DATAS) {
      onSelecionar([...selecionadas, data].sort())
    }
  }

  if (datasDisponiveis.length === 0) {
    return (
      <p className="text-sm text-gray-500 rounded-lg bg-gray-50 px-3 py-2.5">
        Sem datas de agenda abertas. O disparo sai como mensagem simples e o bot
        não assume a conversa.
      </p>
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 p-3 space-y-3">
      <label className="flex items-start gap-2.5 cursor-pointer">
        <input
          type="checkbox"
          checked={ativa}
          onChange={(e) => onAtivar(e.target.checked)}
          className="accent-emerald-600 w-4 h-4 mt-0.5"
        />
        <span className="text-sm text-gray-700">
          O bot conduz o agendamento a partir deste disparo
          <span className="block text-xs text-gray-500 mt-0.5">
            Ele responde, confirma as áreas e fecha o horário. Por 7 dias; depois
            disso a conversa volta a ser atendida só por pessoas.
          </span>
        </span>
      </label>

      {ativa && (
        <div>
          <span className="text-xs font-medium text-gray-500 block mb-1.5">
            Datas que o bot vai oferecer (até {MAX_DATAS})
          </span>
          <div className="flex flex-wrap gap-1.5">
            {datasDisponiveis.map((d) => {
              const marcada = selecionadas.includes(d)
              const cheio = !marcada && selecionadas.length >= MAX_DATAS
              return (
                <button
                  key={d}
                  type="button"
                  disabled={cheio}
                  onClick={() => alterna(d)}
                  className={[
                    'px-2.5 py-1 rounded-md text-sm border transition-colors',
                    marcada
                      ? 'bg-emerald-50 border-emerald-400 text-emerald-800 font-medium'
                      : cheio
                        ? 'border-gray-200 text-gray-300 cursor-not-allowed'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300',
                  ].join(' ')}
                >
                  {rotulo(d)}
                </button>
              )
            })}
          </div>
          {selecionadas.length === 0 && (
            <p className="text-xs text-amber-700 mt-2">
              Sem data selecionada o bot não tem o que oferecer - o disparo sai
              como mensagem simples.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
