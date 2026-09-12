import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useClinicBootstrap } from '@/hooks/useBooking'
import { useCart } from '@/store/useCart'
import { ServiceCard } from '@/components/ServiceCard'
import { CartAddedModal } from '@/components/CartAddedModal'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Service } from '@/types'

export function Home() {
  const { clinicId } = useParams<{ clinicId: string }>()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId as string)
  const cart = useCart()
  const [justAdded, setJustAdded] = useState<Service | null>(null)

  function handleReserve(service: Service) {
    cart.addItem(service)
    setJustAdded(service)
  }

  if (bootstrap.isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    )
  }

  if (bootstrap.isError || !bootstrap.data) {
    return (
      <ErrorState
        message="Não foi possível carregar este salão. Verifique o link e tente novamente."
        onRetry={() => bootstrap.refetch()}
      />
    )
  }

  const { clinic, services } = bootstrap.data

  return (
    <div>
      <div className="mb-8 flex items-center gap-4">
        <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ink-100 font-display text-xl text-ink-600">
          {clinic.logo_url ? (
            <img src={clinic.logo_url} alt={clinic.name} className="h-full w-full object-cover" />
          ) : (
            clinic.name.charAt(0).toUpperCase()
          )}
        </span>
        <div>
          <p className="text-sm text-ink-500">Seja bem vindo(a) ao</p>
          <h1 className="font-display text-2xl text-ink-900">{clinic.display_name || clinic.name}</h1>
        </div>
      </div>

      <h2 className="mb-3 font-display text-lg font-semibold text-ink-900">Serviços</h2>

      {services.length === 0 ? (
        <EmptyState
          title="Nenhum serviço disponível"
          description="Esse salão ainda não cadastrou serviços para agendamento online."
        />
      ) : (
        <div>
          {services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              inCart={cart.items.some((s) => s.id === service.id)}
              onReserve={handleReserve}
            />
          ))}
        </div>
      )}

      <CartAddedModal
        open={justAdded !== null}
        service={justAdded}
        onClose={() => setJustAdded(null)}
        onAddAnother={() => setJustAdded(null)}
        onContinue={() => navigate(`/${clinicId}/agendar`)}
      />
    </div>
  )
}
