import { createBrowserRouter } from 'react-router-dom'
import { CheckinPage } from '@/pages/CheckinPage'
import { DocumentosPage } from '@/pages/DocumentosPage'
import { NotFound } from '@/pages/NotFound'

// Um iPad por clínica, aberto em /:clinicId e travado ali (Acesso Guiado).
// Pelo celular, antes da sessão (PRD 048): /:clinicId/documentos, os mesmos
// passos de termo e ficha, sem chegada nem pagamento.
export const router = createBrowserRouter([
  { path: '/:clinicId/documentos', element: <DocumentosPage /> },
  { path: '/:clinicId', element: <CheckinPage /> },
  { path: '*', element: <NotFound /> },
])
