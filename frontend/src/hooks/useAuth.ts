import { useContext } from 'react'
import { AuthContext } from '@/store/AuthContext'
import type { AuthContextValue } from '@/store/AuthContext'

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
