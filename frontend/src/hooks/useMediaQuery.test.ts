import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMediaQuery, DESKTOP } from './useMediaQuery'

/**
 * O hook decide QUAL componente renderiza - grade ou lista, tabela ou cards.
 * Errar aqui não desalinha um pixel: entrega a tela errada inteira.
 */
function simulaTela(largura: number) {
  const ouvintes = new Set<() => void>()
  let combina = largura >= 768

  vi.stubGlobal('matchMedia', (q: string) => ({
    media: q,
    get matches() {
      return combina
    },
    addEventListener: (_: string, cb: () => void) => ouvintes.add(cb),
    removeEventListener: (_: string, cb: () => void) => ouvintes.delete(cb),
  }))

  return {
    redimensiona(nova: number) {
      combina = nova >= 768
      act(() => ouvintes.forEach((cb) => cb()))
    },
    get quantosOuvintes() {
      return ouvintes.size
    },
  }
}

beforeEach(() => vi.unstubAllGlobals())

describe('useMediaQuery', () => {
  it('já sai com o valor certo no primeiro render', () => {
    // Com useState + useEffect a tela renderizaria uma vez errada e se
    // corrigiria depois - o usuário veria a grade piscar antes da lista.
    simulaTela(375)
    const { result } = renderHook(() => useMediaQuery(DESKTOP))

    expect(result.current).toBe(false)
  })

  it('responde quando a tela muda', () => {
    const tela = simulaTela(375)
    const { result } = renderHook(() => useMediaQuery(DESKTOP))
    expect(result.current).toBe(false)

    tela.redimensiona(1200)

    expect(result.current).toBe(true)
  })

  it('solta o ouvinte ao desmontar', () => {
    const tela = simulaTela(1200)
    const { unmount } = renderHook(() => useMediaQuery(DESKTOP))
    expect(tela.quantosOuvintes).toBe(1)

    unmount()

    expect(tela.quantosOuvintes).toBe(0)
  })

  it('768px é desktop; 767px não', () => {
    simulaTela(768)
    expect(renderHook(() => useMediaQuery(DESKTOP)).result.current).toBe(true)

    simulaTela(767)
    expect(renderHook(() => useMediaQuery(DESKTOP)).result.current).toBe(false)
  })
})
