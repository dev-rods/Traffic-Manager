import { createBrowserRouter } from 'react-router-dom'
import { CheckinPage } from '@/pages/CheckinPage'
import { NotFound } from '@/pages/NotFound'

// Um iPad por clínica, aberto em /:clinicId e travado ali (Acesso Guiado).
export const router = createBrowserRouter([
  { path: '/:clinicId', element: <CheckinPage /> },
  { path: '*', element: <NotFound /> },
])
