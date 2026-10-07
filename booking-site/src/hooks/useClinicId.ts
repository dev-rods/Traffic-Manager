import { useContext } from 'react'
import { ClinicIdContext } from '@/store/clinicIdContext'

export function useClinicId() {
  const ctx = useContext(ClinicIdContext)
  if (!ctx) {
    throw new Error('useClinicId precisa estar dentro de um ClinicIdContext.Provider')
  }
  return ctx
}
