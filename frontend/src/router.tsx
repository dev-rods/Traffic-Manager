import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
import AuthLayout from '@/layouts/AuthLayout'
import { PrivateRoute } from '@/components/PrivateRoute'
import { PublicRoute } from '@/components/PublicRoute'
import LoginPage from '@/pages/auth/LoginPage'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { AgendaPage } from '@/pages/agenda/AgendaPage'
import { PacientesPage } from '@/pages/pacientes/PacientesPage'
import { DocumentosPage } from '@/pages/documentos/DocumentosPage'
import { RelatoriosPage } from '@/pages/relatorios/RelatoriosPage'
import { DescontosPage } from '@/pages/descontos/DescontosPage'
import { DuracaoPage } from '@/pages/duracao/DuracaoPage'
import { ServicosPage } from '@/pages/servicos/ServicosPage'
import { AreasPage } from '@/pages/areas/AreasPage'
import { HorariosPage } from '@/pages/horarios/HorariosPage'
import { FaqPage } from '@/pages/faq/FaqPage'
import { ConfiguracoesPage } from '@/pages/configuracoes/ConfiguracoesPage'
import { ServicosAreasPage } from '@/pages/servicos-areas/ServicosAreasPage'
import { BotPage } from '@/pages/bot/BotPage'
import { LeadsPage } from '@/pages/leads/LeadsPage'
import { UsuariosPage } from '@/pages/usuarios/UsuariosPage'
import { RotaPermitida } from '@/components/RotaPermitida'
import { InicioPorPapel } from '@/components/InicioPorPapel'

export const router = createBrowserRouter([
  {
    // O STAFF nao tem dashboard: mandar todo mundo para la deixaria a
    // funcionaria numa tela que o servidor recusa.
    path: '/',
    element: <InicioPorPapel />,
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
      {
        // Esconder o item no menu resolve o caminho normal; isto resolve o
        // outro, que e alguem colar /relatorios na barra de endereco.
        element: <RotaPermitida />,
        children: [
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'agenda', element: <AgendaPage /> },
          { path: 'pacientes', element: <PacientesPage /> },
          { path: 'pacientes/:patientId/documentos', element: <DocumentosPage /> },
          { path: 'relatorios', element: <RelatoriosPage /> },
          { path: 'descontos', element: <DescontosPage /> },
          { path: 'duracao', element: <DuracaoPage /> },
          { path: 'servicos', element: <ServicosPage /> },
          { path: 'areas', element: <AreasPage /> },
          { path: 'servicos-areas', element: <ServicosAreasPage /> },
          { path: 'horarios', element: <HorariosPage /> },
          { path: 'bot', element: <BotPage /> },
          { path: 'leads', element: <LeadsPage /> },
          { path: 'faq', element: <FaqPage /> },
          { path: 'usuarios', element: <UsuariosPage /> },
          { path: 'configuracoes', element: <ConfiguracoesPage /> },
        ],
      },
    ],
  },
  {
    // Mesma razao do `/`: o STAFF nao tem dashboard.
    path: '*',
    element: <InicioPorPapel />,
  },
])
