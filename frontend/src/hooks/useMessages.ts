import { useState, useCallback } from 'react'
import { messagesService } from '@/services/messages.service'
import type { SendMessagePayload, SendMessageResponse } from '@/services/messages.service'
import { useAuth } from './useAuth'

export interface BatchMessageResult {
  patientId: string
  status: 'sent' | 'queued' | 'failed' | 'pending'
  error?: string
}

export function useSendBatchMessages() {
  const { clinicId } = useAuth()
  const [results, setResults] = useState<BatchMessageResult[]>([])
  const [isSending, setIsSending] = useState(false)
  const [progress, setProgress] = useState({ sent: 0, total: 0 })

  const send = useCallback(async (payloads: SendMessagePayload[]) => {
    if (!clinicId || payloads.length === 0) return

    setIsSending(true)
    setProgress({ sent: 0, total: payloads.length })
    setResults(payloads.map((p) => ({ patientId: p.patient_id, status: 'pending' as const })))

    for (let i = 0; i < payloads.length; i++) {
      const payload = payloads[i]
      try {
        const res: SendMessageResponse = await messagesService.send(clinicId, payload)
        const resultStatus = res.status === 'OK' ? 'sent' as const : 'failed' as const
        setResults((prev) =>
          prev.map((r) =>
            r.patientId === payload.patient_id ? { ...r, status: resultStatus } : r,
          ),
        )
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
  }, [clinicId])

  const reset = useCallback(() => {
    setResults([])
    setProgress({ sent: 0, total: 0 })
  }, [])

  return { send, results, isSending, progress, reset }
}
