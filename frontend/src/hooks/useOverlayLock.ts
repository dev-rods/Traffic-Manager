import { useEffect } from 'react'

/**
 * O comportamento comum de qualquer coisa que cobre a tela: Esc fecha, e o
 * fundo para de rolar enquanto está aberto.
 *
 * Extraído de `Modal.tsx` em 22/09/2026, quando o `Drawer` nasceu precisando
 * exatamente disto. Duas cópias divergem: uma ganha um retorno de foco que a
 * outra não tem, alguém corrige o scroll-lock num lugar só, e a diferença só
 * aparece para o usuário.
 *
 * O contador importa: com um modal aberto sobre um drawer, o primeiro a fechar
 * devolveria o scroll ao fundo com o segundo ainda por cima. Só o último a
 * sair destrava.
 */
let abertos = 0

export function useOverlayLock(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return

    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', aoTeclar)

    abertos += 1
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', aoTeclar)
      abertos -= 1
      if (abertos === 0) document.body.style.overflow = ''
    }
  }, [open, onClose])
}
