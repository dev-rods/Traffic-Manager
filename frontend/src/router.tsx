import { Navigate, createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
import AuthLayout from '@/layouts/AuthLayout'
import { PrivateRoute } from '@/components/PrivateRoute'
import { PublicRoute } from '@/components/PublicRoute'
import LoginPage from '@/pages/auth/LoginPage'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { AgendaPage } from '@/pages/agenda/AgendaPage'
import { PacientesPage } from '@/pages/pacientes/PacientesPage'
import { RelatoriosPage } from '@/pages/relatorios/RelatoriosPage'
import { DescontosPage } from '@/pages/descontos/DescontosPage'
import { ServicosPage } from '@/pages/servicos/ServicosPage'
import { AreasPage } from '@/pages/areas/AreasPage'
import { HorariosPage } from '@/pages/horarios/HorariosPage'
import { FaqPage } from '@/pages/faq/FaqPage'
import { ConfiguracoesPage } from '@/pages/configuracoes/ConfiguracoesPage'
import { ServicosAreasPage } from '@/pages/servicos-areas/ServicosAreasPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: '/login',
    element: (
      <PublicRoute>
        <AuthLayout>
          <LoginPage />
        </AuthLayout>
      </PublicRoute>
    ),
  },
  {
    path: '/',
    element: (
      <PrivateRoute>
        <AppLayout />
      </PrivateRoute>
    ),
    children: [
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'agenda', element: <AgendaPage /> },
      { path: 'pacientes', element: <PacientesPage /> },
      { path: 'relatorios', element: <RelatoriosPage /> },
      { path: 'descontos', element: <DescontosPage /> },
      { path: 'servicos', element: <ServicosPage /> },
      { path: 'areas', element: <AreasPage /> },
      { path: 'servicos-areas', element: <ServicosAreasPage /> },
      { path: 'horarios', element: <HorariosPage /> },
      { path: 'faq', element: <FaqPage /> },
      { path: 'configuracoes', element: <ConfiguracoesPage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
])
