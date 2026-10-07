import type { MetodoLaser, SkinType } from '@/types'
import { avisos } from '@/lib/protocolo'

interface AvisosDoProtocoloProps {
  metodo: MetodoLaser | null
  skinType: SkinType | null
  bronzeada: boolean
}

/**
 * Os avisos dos materiais da clínica, palavra por palavra.
 *
 * Avisar e não bloquear é decisão registrada no PRD 012: quem decide conduta é
 * quem aplica, e software que impede acaba contornado por fora — e aí a sessão
 * acontece sem registro nenhum, que é pior que a sessão registrada com um aviso
 * ignorado.
 */
export function AvisosDoProtocolo({ metodo, skinType, bronzeada }: AvisosDoProtocoloProps) {
  const textos = avisos(metodo, skinType, bronzeada)
  if (textos.length === 0) return null

  return (
    <ul className="mt-2 space-y-1.5" role="status">
      {textos.map((texto) => (
        <li
          key={texto}
          className="flex gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900"
        >
          <span aria-hidden="true" className="select-none">⚠</span>
          <span>{texto}</span>
        </li>
      ))}
    </ul>
  )
}
