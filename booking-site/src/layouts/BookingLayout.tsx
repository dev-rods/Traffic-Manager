import { useParams } from 'react-router-dom'
import { CartProvider } from '@/store/CartProvider'
import { ClinicIdContext } from '@/store/clinicIdContext'
import { BookingChrome } from './BookingChrome'

/** Domínio padrão (*.vercel.app / localhost): clinicId vem do path, igual
 * sempre foi. Ver CustomDomainLayout pro caso de domínio próprio. */
export function BookingLayout() {
  const { clinicId } = useParams<{ clinicId: string }>()

  if (!clinicId) return null

  return (
    <ClinicIdContext.Provider value={{ clinicId, basePath: `/${clinicId}` }}>
      <CartProvider key={clinicId}>
        <BookingChrome />
      </CartProvider>
    </ClinicIdContext.Provider>
  )
}
