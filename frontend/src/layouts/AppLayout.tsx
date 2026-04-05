import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useBranding } from '@/hooks/useBranding'
import { useTheme } from '@/hooks/useTheme'

// ── SVG Icon components (Lucide-style, 24x24) ──────────────
function Icon({ d, className = '' }: { d: string; className?: string }) {
  return (
    <svg className={`w-[18px] h-[18px] ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}

function IconHome() { return <Icon d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" /> }
function IconCalendar() { return <Icon d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /> }
function IconUsers() { return <Icon d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zm14 10v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" /> }
function IconChart() { return <Icon d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /> }
function IconSparkles() { return <Icon d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /> }
function IconGrid() { return <Icon d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /> }
function IconLink() { return <Icon d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /> }
function IconTag() { return <Icon d="M7 7h.01M7 3h5a1.99 1.99 0 011.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.99 1.99 0 013 12V7a4 4 0 014-4z" /> }
function IconClock() { return <Icon d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /> }
function IconBot() { return <Icon d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.3 24.3 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-1.5 4.5H6.5L5 14.5m14 0H5m14 0l-.938-2.813M5 14.5l.938-2.813M12 20.5v-2" /> }
function IconTarget() { return <Icon d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" /> }
function IconHelp() { return <Icon d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /> }
function IconSettings() { return <Icon d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z M15 12a3 3 0 11-6 0 3 3 0 016 0z" /> }
function IconLogout() { return <Icon d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /> }

const ICON_MAP: Record<string, () => React.ReactNode> = {
  '/dashboard': () => <IconHome />,
  '/agenda': () => <IconCalendar />,
  '/pacientes': () => <IconUsers />,
  '/relatorios': () => <IconChart />,
  '/servicos': () => <IconSparkles />,
  '/areas': () => <IconGrid />,
  '/servicos-areas': () => <IconLink />,
  '/descontos': () => <IconTag />,
  '/horarios': () => <IconClock />,
  '/bot': () => <IconBot />,
  '/leads': () => <IconTarget />,
  '/faq': () => <IconHelp />,
  '/configuracoes': () => <IconSettings />,
}

interface NavItemDef {
  to: string
  label: string
}

interface NavGroup {
  label: string
  items: NavItemDef[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: '',
    items: [
      { to: '/dashboard', label: 'Dashboard' },
      { to: '/agenda', label: 'Agenda' },
      { to: '/pacientes', label: 'Pacientes' },
      { to: '/relatorios', label: 'Relatórios' },
    ],
  },
  {
    label: 'Catálogo',
    items: [
      { to: '/servicos', label: 'Serviços' },
      { to: '/areas', label: 'Áreas' },
      { to: '/servicos-areas', label: 'Serviços & Áreas' },
      { to: '/descontos', label: 'Descontos' },
      { to: '/horarios', label: 'Horários' },
    ],
  },
  {
    label: 'WhatsApp',
    items: [
      { to: '/bot', label: 'Bot' },
      { to: '/leads', label: 'Leads' },
      { to: '/faq', label: 'FAQ' },
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
  const { isDark, setTheme } = useTheme()
  useBranding(clinic?.display_name || clinic?.name)

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
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-[#0f1117]">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white dark:bg-[#16181d] border-r border-gray-200 dark:border-gray-800 flex flex-col h-screen">
        {/* Clinic branding */}
        <div className="px-5 py-5 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
              {clinic?.name?.[0]?.toUpperCase() ?? 'C'}
            </div>
            <div className="min-w-0">
              <p className="font-bold text-gray-800 dark:text-gray-100 text-sm leading-tight truncate">
                {clinic?.display_name || clinic?.name || 'Carregando...'}
              </p>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 truncate">
                {clinic?.owner_email ?? ''}
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-1">
          {NAV_GROUPS.map((group) => {
            const isOpen = openGroups.has(group.label)
            const hasActiveChild = group.items.some((item) => location.pathname.startsWith(item.to))

            if (!group.label) {
              return (
                <div key="top" className="space-y-0.5">
                  {group.items.map((item) => (
                    <SidebarLink key={item.to} {...item} />
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
                    hasActiveChild ? 'text-brand-400' : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300',
                  ].join(' ')}
                >
                  {group.label}
                  <svg
                    className={['w-3.5 h-3.5 transition-transform duration-150', isOpen ? 'rotate-180' : ''].join(' ')}
                    viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  >
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                {isOpen && (
                  <div className="mt-0.5 space-y-0.5">
                    {group.items.map((item) => (
                      <SidebarLink key={item.to} {...item} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SidebarLink to="/configuracoes" label="Configurações" className="px-6" />
        </div>
        <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <button
            onClick={logout}
            className="flex items-center gap-2.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors cursor-pointer"
          >
            <IconLogout />
            <span className="text-xs font-medium">Sair</span>
          </button>
          <button
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            title={isDark ? 'Modo claro' : 'Modo escuro'}
            className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          >
            {isDark ? (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
              </svg>
            )}
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

function SidebarLink({ to, label, className = '' }: NavItemDef & { className?: string }) {
  const renderIcon = ICON_MAP[to]
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300'
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200',
          className,
        ].join(' ')
      }
    >
      {renderIcon ? renderIcon() : null}
      {label}
    </NavLink>
  )
}
