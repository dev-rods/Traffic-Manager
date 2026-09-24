import { useSyncExternalStore } from 'react'

/**
 * Responde a uma media query, e volta a responder quando ela muda.
 *
 * Existe para as decisões que NÃO dá para tomar com classe CSS. Esconder algo
 * abaixo de `md` é trabalho do Tailwind (`hidden md:block`); escolher **outro
 * componente** - a lista do dia no lugar da grade da semana - é decisão de
 * render, e precisa do valor em JavaScript.
 *
 * `useSyncExternalStore` e não `useState` + `useEffect`: o valor já sai certo
 * no primeiro render, sem o piscar de renderizar o layout errado e corrigir
 * logo depois.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notificar) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', notificar)
      return () => mql.removeEventListener('change', notificar)
    },
    () => window.matchMedia(query).matches,
    // No servidor não há tela. `false` mantém o layout mobile como padrão, que
    // é o que degrada melhor se algum dia houver SSR.
    () => false,
  )
}

/** O limiar do painel inteiro. Abaixo disto é celular. */
export const DESKTOP = '(min-width: 768px)'

/** Atalho legível: `const ehDesktop = useEhDesktop()`. */
export function useEhDesktop(): boolean {
  return useMediaQuery(DESKTOP)
}
