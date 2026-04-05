import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

interface NavItem {
  to: string
  label: string
  icon: string
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: '',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: '🏠' },
      { to: '/agenda', label: 'Agenda', icon: '📅' },
      { to: '/pacientes', label: 'Pacientes', icon: '👥' },
      { to: '/relatorios', label: 'Relatórios', icon: '📊' },
    ],
  },
  {
    label: 'Catálogo',
    items: [
      { to: '/servicos', label: 'Serviços', icon: '💆' },
      { to: '/areas', label: 'Áreas', icon: '📋' },
      { to: '/servicos-areas', label: 'Serviços & Áreas', icon: '🔗' },
      { to: '/descontos', label: 'Descontos', icon: '🏷' },
      { to: '/horarios', label: 'Horários', icon: '🕐' },
    ],
  },
  {
    label: 'WhatsApp',
    items: [
      { to: '/bot', label: 'Bot', icon: '🤖' },
      { to: '/leads', label: 'Leads', icon: '🎯' },
      { to: '/faq', label: 'FAQ', icon: '❓' },
    ],
  },
]

function useActiveGroup(): string {
  const { pathname } = useLocation()
  for (const group of NAV_GROUPS) {
    if (group.items.some((item) => pathname.startsWith(item.to))) {
      return group.label
    }
  }
  return ''
}

export default function AppLayout() {
  const { clinic, logout } = useAuth()
  const activeGroupLabel = useActiveGroup()
  const [openGroups, setOpenGroups] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    initial.add('')
    if (activeGroupLabel) initial.add(activeGroupLabel)
    return initial
  })

  const toggleGroup = (label: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

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
        <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-1">
          {NAV_GROUPS.map((group) => {
            const isOpen = openGroups.has(group.label)
            const hasActiveChild = group.items.some((item) => location.pathname.startsWith(item.to))

            // Top-level group (no label) — always visible
            if (!group.label) {
              return (
                <div key="top" className="space-y-0.5">
                  {group.items.map((item) => (
                    <NavItem key={item.to} {...item} />
                  ))}
                </div>
              )
            }

            return (
              <div key={group.label} className="pt-2">
                <button
                  onClick={() => toggleGroup(group.label)}
                  className={[
                    'w-full flex items-center justify-between px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider transition-colors cursor-pointer rounded',
                    hasActiveChild ? 'text-brand-600' : 'text-gray-400 hover:text-gray-600',
                  ].join(' ')}
                >
                  {group.label}
                  <svg
                    className={['w-3.5 h-3.5 transition-transform duration-150', isOpen ? 'rotate-180' : ''].join(' ')}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                {isOpen && (
                  <div className="mt-0.5 space-y-0.5">
                    {group.items.map((item) => (
                      <NavItem key={item.to} {...item} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* Footer: Settings + User */}
        <div className="border-t border-gray-100">
          <NavLink
            to="/configuracoes"
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-6 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-100 text-brand-700'
                  : 'text-gray-500 hover:bg-gray-100',
              ].join(' ')
            }
          >
            <span className="text-base">⚙</span>
            Configurações
          </NavLink>
        </div>
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
            className="text-gray-400 hover:text-gray-600 text-lg transition-colors ml-1 cursor-pointer"
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

function NavItem({ to, label, icon }: NavItem) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'bg-brand-100 text-brand-700'
            : 'text-gray-500 hover:bg-gray-100',
        ].join(' ')
      }
    >
      <span className="text-base">{icon}</span>
      {label}
    </NavLink>
  )
}
