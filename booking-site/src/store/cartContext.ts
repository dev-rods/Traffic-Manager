import { createContext } from 'react'
import type { Service } from '@/types'

export interface CartContextValue {
  items: Service[]
  addItem: (service: Service) => void
  removeItem: (serviceId: string) => void
  clearCart: () => void
  professionalId: string | null
  setProfessionalId: (id: string | null) => void
  date: string | null
  time: string | null
  setDate: (date: string) => void
  setSchedule: (date: string, time: string) => void
  clearSchedule: () => void
  customerName: string
  customerPhone: string
  setCustomer: (name: string, phone: string) => void
  otpToken: string | null
  setOtpToken: (token: string | null) => void
  totalDurationMinutes: number
  totalPriceCents: number
}

export const CartContext = createContext<CartContextValue | null>(null)
