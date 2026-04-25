import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { patientsService } from '@/services/patients.service'
import type { ListPatientsParams } from '@/services/patients.service'
import type { CreatePatientPayload, CreatePatientResponse } from '@/types'
import { useAuth } from './useAuth'

export interface BatchDeleteResult {
  patientId: string
  status: 'pending' | 'deleted' | 'failed'
  error?: string
}

export const patientKeys = {
  all: ['patients'] as const,
  lists: () => [...patientKeys.all, 'list'] as const,
  list: (clinicId: string, params?: ListPatientsParams) =>
    [...patientKeys.lists(), clinicId, params] as const,
}

export function usePatients(params?: ListPatientsParams) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: patientKeys.list(clinicId!, params),
    queryFn: () => patientsService.list(clinicId!, params),
    enabled: !!clinicId,
  })
}

export function useCreatePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation<CreatePatientResponse, Error, CreatePatientPayload>({
    mutationFn: (payload) => patientsService.create(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}

export function useUpdatePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, data }: { patientId: string; data: Partial<CreatePatientPayload> }) =>
      patientsService.update(clinicId!, patientId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}

export function useDeletePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => patientsService.delete(clinicId!, patientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}

export function useBatchDeletePatients() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  const [results, setResults] = useState<BatchDeleteResult[]>([])
  const [isDeleting, setIsDeleting] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const runningRef = useRef(false)

  const run = useCallback(async (patientIds: string[]) => {
    if (!clinicId || patientIds.length === 0) return
    if (runningRef.current) return
    runningRef.current = true

    setIsDeleting(true)
    setProgress({ done: 0, total: patientIds.length })
    setResults(patientIds.map((id) => ({ patientId: id, status: 'pending' as const })))

    for (let i = 0; i < patientIds.length; i++) {
      const id = patientIds[i]
      try {
        await patientsService.delete(clinicId, id)
        setResults((prev) =>
          prev.map((r) => (r.patientId === id ? { ...r, status: 'deleted' as const } : r)),
        )
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Erro desconhecido'
        setResults((prev) =>
          prev.map((r) =>
            r.patientId === id ? { ...r, status: 'failed' as const, error: message } : r,
          ),
        )
      }
      setProgress({ done: i + 1, total: patientIds.length })
    }

    setIsDeleting(false)
    runningRef.current = false
    queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
  }, [clinicId, queryClient])

  const reset = useCallback(() => {
    setResults([])
    setProgress({ done: 0, total: 0 })
  }, [])

  return { run, results, isDeleting, progress, reset }
}
