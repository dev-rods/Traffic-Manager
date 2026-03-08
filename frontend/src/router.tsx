import { Navigate, createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
import AuthLayout from '@/layouts/AuthLayout'
import { PrivateRoute } from '@/components/PrivateRoute'
import { PublicRoute } from '@/components/PublicRoute'
import LoginPage from '@/pages/auth/LoginPage'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import AgendaPage from '@/pages/agenda/AgendaPage'
import { PacientesPage } from '@/pages/pacientes/PacientesPage'
import RelatoriosPage from '@/pages/relatorios/RelatoriosPage'

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
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
])
