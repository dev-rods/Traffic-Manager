import { useQuery } from '@tanstack/react-query'
import { bookingService } from '@/services/booking.service'
import { CartProvider } from '@/store/CartProvider'
import { ClinicIdContext } from '@/store/clinicIdContext'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorState } from '@/components/ui/ErrorState'
import { BookingChrome } from './BookingChrome'

/** Domínio próprio de uma clínica (ver "Domínio customizado" no painel): não
 * há clinicId no path, a raiz do site JÁ é a clínica. Resolve qual é, pelo
 * hostname, antes de montar o resto da árvore. */
export function CustomDomainLayout() {
  const host = window.location.hostname

  const query = useQuery({
    queryKey: ['resolve-domain', host],
    queryFn: () => bookingService.resolveDomain(host),
    staleTime: Infinity,
    retry: 1,
  })

  if (query.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (query.isError || !query.data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <ErrorState
          message="Este endereço não está associado a nenhum salão."
          onRetry={() => query.refetch()}
        />
      </div>
    )
  }

  return (
    <ClinicIdContext.Provider value={{ clinicId: query.data, basePath: '' }}>
      <CartProvider key={query.data}>
        <BookingChrome />
      </CartProvider>
    </ClinicIdContext.Provider>
  )
}
