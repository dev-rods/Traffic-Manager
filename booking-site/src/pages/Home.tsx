import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useClinicBootstrap } from '@/hooks/useBooking'
import { useClinicId } from '@/hooks/useClinicId'
import { useCart } from '@/store/useCart'
import { ServiceCard } from '@/components/ServiceCard'
import { ClinicWelcome } from '@/components/ClinicWelcome'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { CartAddedModal } from '@/components/CartAddedModal'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Service } from '@/types'

export function Home() {
  const { clinicId, basePath } = useClinicId()
  const navigate = useNavigate()
  const bootstrap = useClinicBootstrap(clinicId)
  const cart = useCart()
  const [justAdded, setJustAdded] = useState<Service | null>(null)

  const services = bootstrap.data?.services
  const singleService = services?.length === 1 ? services[0] : null

  // Um único serviço ativo: nem mostramos a etapa de escolha, igual ao bot
  // (ConversationEngine._on_enter_select_services: "single service -> auto-selecting").
  // Vale também com o serviço já no carrinho (vindo do "Agende online" do
  // topo, ou do voltar do navegador): a lista com um item só e "Adicionado"
  // confundia, porque não há o que escolher.
  useEffect(() => {
    if (!singleService) return
    if (!cart.items.some((i) => i.service.id === singleService.id)) cart.addItem(singleService)
    navigate(`${basePath}/agendar`, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [singleService?.id])

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

  // Com um serviço só, o efeito acima sempre redireciona: aqui só se espera
  // por ele. (Antes o redirecionamento dependia de o carrinho estar vazio e,
  // com ele cheio, a tela travava no spinner; agora o efeito não depende mais
  // do carrinho.)
  if (singleService) {
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

  const { clinic } = bootstrap.data

  return (
    <div>
      <div className="mb-6 border-b border-ink-200 pb-6">
        <ClinicWelcome clinic={clinic} />
      </div>

      <SectionTitle>Serviços</SectionTitle>

      {services && services.length === 0 ? (
        <EmptyState
          title="Nenhum serviço disponível"
          description="Esse salão ainda não cadastrou serviços para agendamento online."
        />
      ) : (
        <div>
          {services?.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              inCart={cart.items.some((i) => i.service.id === service.id)}
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
        onContinue={() => navigate(`${basePath}/agendar`)}
      />
    </div>
  )
}
