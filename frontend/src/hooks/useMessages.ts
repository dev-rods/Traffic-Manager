import { useState, useCallback, useRef } from 'react'
import { messagesService } from '@/services/messages.service'
import type { SendMessagePayload, SendMessageResponse, DeliveryState } from '@/services/messages.service'
import { useAuth } from './useAuth'

export interface BatchMessageResult {
  patientId: string
  status: 'sent' | 'queued' | 'failed' | 'pending'
  error?: string
  providerMessageId?: string
  sentAtIso?: string
  delivery?: DeliveryState | 'checking'
}

const DELIVERY_POLL_INTERVAL_MS = 10_000
const DELIVERY_POLL_MAX_ATTEMPTS = 6

export function useSendBatchMessages() {
  const { clinicId } = useAuth()
  const [results, setResults] = useState<BatchMessageResult[]>([])
  const [isSending, setIsSending] = useState(false)
  const [isCheckingDelivery, setIsCheckingDelivery] = useState(false)
  const [progress, setProgress] = useState({ sent: 0, total: 0 })
  const sendingRef = useRef(false)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const pollDelivery = useCallback(async (
    cid: string,
    sends: Array<{ providerMessageId: string; sentAtIso: string }>,
  ) => {
    let attempt = 0
    let pending = new Map<string, { sentAtIso: string }>()
    for (const s of sends) pending.set(s.providerMessageId, { sentAtIso: s.sentAtIso })

    const tick = async () => {
      attempt += 1
      const query = Array.from(pending.entries()).map(([pmid, v]) => ({
        providerMessageId: pmid,
        sentAtIso: v.sentAtIso,
      }))
      try {
        const resp = await messagesService.getDeliveryStatus(cid, query)
        const nextPending = new Map(pending)
        setResults((prev) =>
          prev.map((r) => {
            if (!r.providerMessageId) return r
            const item = resp.results.find((x) => x.providerMessageId === r.providerMessageId)
            if (!item) return r
            if (item.delivery === 'delivered') {
              nextPending.delete(r.providerMessageId)
              return { ...r, delivery: 'delivered' }
            }
            return r
          }),
        )
        pending = nextPending
      } catch {
        // Silencia — próxima iteração tenta de novo. Se o backend estiver fora,
        // o estado final "checking" vai virar "sent_only" no timeout.
      }

      if (pending.size === 0 || attempt >= DELIVERY_POLL_MAX_ATTEMPTS) {
        if (pending.size > 0) {
          const stillPending = new Set(pending.keys())
          setResults((prev) =>
            prev.map((r) =>
              r.providerMessageId && stillPending.has(r.providerMessageId) && r.delivery === 'checking'
                ? { ...r, delivery: 'sent_only' }
                : r,
            ),
          )
        }
        setIsCheckingDelivery(false)
        pollTimeoutRef.current = null
        return
      }

      pollTimeoutRef.current = setTimeout(() => { void tick() }, DELIVERY_POLL_INTERVAL_MS)
    }

    pollTimeoutRef.current = setTimeout(() => { void tick() }, DELIVERY_POLL_INTERVAL_MS)
  }, [])

  const send = useCallback(async (payloads: SendMessagePayload[]) => {
    if (!clinicId || payloads.length === 0) return
    if (sendingRef.current) return
    sendingRef.current = true

    setIsSending(true)
    setProgress({ sent: 0, total: payloads.length })
    setResults(payloads.map((p) => ({ patientId: p.patient_id, status: 'pending' as const })))

    const sentForPolling: Array<{ providerMessageId: string; sentAtIso: string }> = []

    for (let i = 0; i < payloads.length; i++) {
      const payload = payloads[i]
      const sentAtIso = new Date().toISOString()
      try {
        const res: SendMessageResponse = await messagesService.send(clinicId, payload)
        const wasSent = res.status === 'SUCCESS'
        const providerMessageId = res.providerMessageId ?? ''
        setResults((prev) =>
          prev.map((r) =>
            r.patientId === payload.patient_id
              ? {
                  ...r,
                  status: wasSent ? 'sent' : 'failed',
                  providerMessageId: wasSent ? providerMessageId : undefined,
                  sentAtIso: wasSent ? sentAtIso : undefined,
                  delivery: wasSent ? 'checking' : undefined,
                }
              : r,
          ),
        )
        if (wasSent && providerMessageId) {
          sentForPolling.push({ providerMessageId, sentAtIso })
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Erro desconhecido'
        setResults((prev) =>
          prev.map((r) =>
            r.patientId === payload.patient_id ? { ...r, status: 'failed', error: message } : r,
          ),
        )
      }
      setProgress({ sent: i + 1, total: payloads.length })
    }

    setIsSending(false)
    sendingRef.current = false

    if (sentForPolling.length > 0) {
      setIsCheckingDelivery(true)
      void pollDelivery(clinicId, sentForPolling)
    }
  }, [clinicId, pollDelivery])

  const reset = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    setResults([])
    setProgress({ sent: 0, total: 0 })
    setIsCheckingDelivery(false)
  }, [])

  return { send, results, isSending, isCheckingDelivery, progress, reset }
}
