import { useState } from 'react'
import { Outlet, useParams } from 'react-router-dom'
import { CartProvider } from '@/store/CartProvider'
import { MyAppointmentsModal } from '@/components/MyAppointmentsModal'
import { Button } from '@/components/ui/Button'

export function BookingLayout() {
  const { clinicId } = useParams<{ clinicId: string }>()
  const [myAppointmentsOpen, setMyAppointmentsOpen] = useState(false)

  if (!clinicId) return null

  return (
    <CartProvider key={clinicId}>
      <div className="min-h-screen bg-ink-50">
        <header className="flex items-center justify-between border-b border-ink-100 bg-white px-6 py-4 sm:px-10">
          <span className="font-display text-lg tracking-wide text-ink-900">Agende online</span>
          <Button variant="ghost" size="sm" onClick={() => setMyAppointmentsOpen(true)}>
            Meus agendamentos
          </Button>
        </header>
        <main className="mx-auto max-w-2xl px-6 py-10 sm:px-10">
          <Outlet />
        </main>
      </div>
      <MyAppointmentsModal
        open={myAppointmentsOpen}
        clinicId={clinicId}
        onClose={() => setMyAppointmentsOpen(false)}
      />
    </CartProvider>
  )
}
