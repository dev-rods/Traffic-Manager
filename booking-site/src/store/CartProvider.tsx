import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Service } from '@/types'
import { CartContext } from './cartContext'
import type { CartContextValue } from './cartContext'

/**
 * Mantido pelo <BookingLayout> com `key={clinicId}` — trocar de salão remonta
 * o provider (estado limpo) em vez de resetar campo a campo em um efeito.
 */
export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Service[]>([])
  const [professionalId, setProfessionalId] = useState<string | null>(null)
  const [date, setDateState] = useState<string | null>(null)
  const [time, setTime] = useState<string | null>(null)
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [otpToken, setOtpToken] = useState<string | null>(null)

  function addItem(service: Service) {
    setItems((prev) => (prev.some((s) => s.id === service.id) ? prev : [...prev, service]))
    setDateState(null)
    setTime(null)
  }

  function removeItem(serviceId: string) {
    setItems((prev) => prev.filter((s) => s.id !== serviceId))
    setDateState(null)
    setTime(null)
  }

  function clearCart() {
    setItems([])
    setProfessionalId(null)
    setDateState(null)
    setTime(null)
    setOtpToken(null)
  }

  function setDateOnly(nextDate: string) {
    setDateState(nextDate)
    setTime(null)
  }

  function setSchedule(nextDate: string, nextTime: string) {
    setDateState(nextDate)
    setTime(nextTime)
  }

  function clearSchedule() {
    setDateState(null)
    setTime(null)
  }

  function setCustomer(name: string, phone: string) {
    setCustomerName(name)
    setCustomerPhone(phone)
  }

  const totalDurationMinutes = useMemo(
    () => items.reduce((sum, s) => sum + s.duration_minutes, 0),
    [items]
  )
  const totalPriceCents = useMemo(
    () => items.reduce((sum, s) => sum + (s.price_cents ?? 0), 0),
    [items]
  )

  const value: CartContextValue = {
    items,
    addItem,
    removeItem,
    clearCart,
    professionalId,
    setProfessionalId,
    date,
    time,
    setDate: setDateOnly,
    setSchedule,
    clearSchedule,
    customerName,
    customerPhone,
    setCustomer,
    otpToken,
    setOtpToken,
    totalDurationMinutes,
    totalPriceCents,
  }

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
