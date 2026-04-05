import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: '🏠' },
  { to: '/agenda', label: 'Agenda', icon: '📅' },
  { to: '/pacientes', label: 'Pacientes', icon: '👥' },
  { to: '/relatorios', label: 'Relatórios', icon: '📊' },
  { to: '/servicos', label: 'Serviços', icon: '💆' },
  { to: '/areas', label: 'Áreas', icon: '📋' },
  { to: '/descontos', label: 'Descontos', icon: '🏷' },
  { to: '/horarios', label: 'Horários', icon: '🕐' },
  { to: '/faq', label: 'FAQ', icon: '❓' },
  { to: '/configuracoes', label: 'Configurações', icon: '⚙' },
]

export default function AppLayout() {
  const { clinic, logout } = useAuth()

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col h-screen">
        {/* Clinic branding */}
        <div className="px-5 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold text-sm">
              {clinic?.name?.[0] ?? 'T'}
            </div>
            <div className="min-w-0">
              <p className="font-bold text-gray-800 text-sm leading-tight truncate">
                {clinic?.name ?? 'Traffic Manager'}
              </p>
              <p className="text-xs text-gray-400">✨ Estética</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-100 text-brand-700'
                    : 'text-gray-500 hover:bg-gray-100',
                ].join(' ')
              }
            >
              <span className="text-lg">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-full bg-brand-100 flex-shrink-0 flex items-center justify-center text-brand-700 font-bold text-xs">
              {clinic?.owner_email?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <p className="text-xs font-semibold text-gray-700 truncate">
              {clinic?.owner_email ?? 'Proprietário'}
            </p>
          </div>
          <button
            onClick={logout}
            title="Sair"
            className="text-gray-400 hover:text-gray-600 text-lg transition-colors ml-1"
          >
            ⎋
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
