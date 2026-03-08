import { useContext } from 'react'
import { AuthContext } from '@/store/auth-context'
import type { AuthContextValue } from '@/store/auth-context'

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
