import { useEffect, useState } from 'react'
import { Link, Outlet, useParams } from 'react-router-dom'
import { CartProvider } from '@/store/CartProvider'
import { MyAppointmentsModal } from '@/components/MyAppointmentsModal'
import { Button } from '@/components/ui/Button'
import { useClinicBootstrap } from '@/hooks/useBooking'

function useDynamicFavicon(faviconUrl: string | null | undefined) {
  useEffect(() => {
    if (!faviconUrl) return
    let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = faviconUrl
  }, [faviconUrl])
}

export function BookingLayout() {
  const { clinicId } = useParams<{ clinicId: string }>()
  const [myAppointmentsOpen, setMyAppointmentsOpen] = useState(false)
  const bootstrap = useClinicBootstrap(clinicId as string)
  const clinic = bootstrap.data?.clinic

  useDynamicFavicon(clinic?.favicon_url)

  if (!clinicId) return null

  return (
    <CartProvider key={clinicId}>
      <div className="min-h-screen bg-ink-50">
        <header className="flex items-center justify-between border-b border-ink-100 bg-white px-6 py-4 sm:px-10">
          <Link to={`/${clinicId}`} className="flex items-center transition-opacity hover:opacity-70">
            {clinic?.logo_url ? (
              <img
                src={clinic.logo_url}
                alt={clinic.display_name || clinic.name}
                className="h-9 w-9 rounded-full object-cover"
              />
            ) : (
              <span className="font-display text-lg tracking-wide text-ink-900">Agende online</span>
            )}
          </Link>
          <Button variant="muted" size="sm" onClick={() => setMyAppointmentsOpen(true)}>
            Meus agendamentos
          </Button>
        </header>
        <main className="mx-auto max-w-[960px] px-6 py-10 sm:px-10">
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
