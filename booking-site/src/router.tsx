import { createBrowserRouter } from 'react-router-dom'
import { BookingLayout } from '@/layouts/BookingLayout'
import { CustomDomainLayout } from '@/layouts/CustomDomainLayout'
import { Home } from '@/pages/Home'
import { Booking } from '@/pages/Booking'
import { NotFound } from '@/pages/NotFound'
import { isDefaultDomain } from '@/utils/domain'

const children = [
  { index: true, element: <Home /> },
  { path: 'agendar', element: <Booking /> },
]

// No domínio padrão o clinicId vem do path (/:clinicId); num domínio próprio
// de clínica (ver CustomDomainField no painel) a raiz JÁ é a clínica, e quem
// descobre qual é o CustomDomainLayout, pelo hostname. As duas árvores nunca
// coexistem: decidido uma vez, no boot, pelo host que o navegador mandou.
export const router = isDefaultDomain(window.location.hostname)
  ? createBrowserRouter([
      { path: '/:clinicId', element: <BookingLayout />, children },
      { path: '*', element: <NotFound /> },
    ])
  : createBrowserRouter([{ path: '/', element: <CustomDomainLayout />, children }])
