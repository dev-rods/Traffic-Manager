import { useEffect, useRef } from 'react'

const EVENTS = ['pointerdown', 'keydown', 'touchstart', 'wheel'] as const

/**
 * Chama `onIdle` depois de `ms` sem nenhum toque. É o que impede a próxima
 * paciente de encontrar na tela o agendamento (e o token) da anterior, que
 * saiu no meio do check-in.
 */
export function useIdleReset(ms: number, onIdle: () => void, enabled: boolean) {
  const callback = useRef(onIdle)
  useEffect(() => {
    callback.current = onIdle
  }, [onIdle])

  useEffect(() => {
    if (!enabled) return
    let timer = window.setTimeout(() => callback.current(), ms)
    const restart = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => callback.current(), ms)
    }
    EVENTS.forEach((e) => window.addEventListener(e, restart, { passive: true }))
    return () => {
      window.clearTimeout(timer)
      EVENTS.forEach((e) => window.removeEventListener(e, restart))
    }
  }, [ms, enabled])
}
