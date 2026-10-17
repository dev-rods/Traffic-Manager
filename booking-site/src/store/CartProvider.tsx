import { useState } from 'react'
import type { ReactNode } from 'react'
import type { CartItem, Service } from '@/types'
import { CartContext } from './cartContext'
import type { CartContextValue } from './cartContext'

/**
 * Mantido pelo <BookingLayout> com `key={clinicId}` — trocar de salão remonta
 * o provider (estado limpo) em vez de resetar campo a campo em um efeito.
 *
 * Duração, preço e desconto não vivem aqui (nem no front): o backend os
 * calcula a partir do carrinho (`toCartPayload` em `utils/cartTotals.ts`),
 * com as mesmas regras do bot de WhatsApp. Profissional também não: quem
 * atribui é o backend.
 */
export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([])
  const [date, setDateState] = useState<string | null>(null)
  const [time, setTime] = useState<string | null>(null)
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')

  function addItem(service: Service) {
    setItems((prev) => (prev.some((i) => i.service.id === service.id) ? prev : [...prev, { service, areaIds: [] }]))
    setDateState(null)
    setTime(null)
  }

  function removeItem(serviceId: string) {
    setItems((prev) => prev.filter((i) => i.service.id !== serviceId))
    setDateState(null)
    setTime(null)
  }

  function setItemAreas(serviceId: string, areaIds: string[]) {
    setItems((prev) => prev.map((i) => (i.service.id === serviceId ? { ...i, areaIds } : i)))
    setDateState(null)
    setTime(null)
  }

  function clearCart() {
    setItems([])
    setDateState(null)
    setTime(null)
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

  const value: CartContextValue = {
    items,
    addItem,
    removeItem,
    setItemAreas,
    clearCart,
    date,
    time,
    setDate: setDateOnly,
    setSchedule,
    clearSchedule,
    customerName,
    customerPhone,
    setCustomer,
  }

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
