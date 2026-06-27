import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ChevronDown, LayoutDashboard, Monitor, BarChart2, AlertCircle, Layers, Package, Terminal, Network, Globe, BrainCircuit, Gauge, Code2, ClipboardList, Wand2, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

type NavItem = {
  to: string
  label: string
  icon: React.ComponentType<{ size?: number }>
}

type NavSection = {
  id: string
  label: string
  items: NavItem[]
}

const NAV_SECTIONS: NavSection[] = [
  {
    id: 'core',
    label: 'Core Platform',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/onboarding', label: 'Onboarding', icon: Wand2 },
      { to: '/devices', label: 'Devices', icon: Monitor },
      { to: '/plugins', label: 'Plugins', icon: Package },
      { to: '/executions', label: 'Executions', icon: Terminal },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { to: '/ports', label: 'Ports', icon: Network },
      { to: '/webservices', label: 'Webservices', icon: Globe },
      { to: '/telemetry', label: 'Telemetry', icon: BarChart2 },
      { to: '/slo', label: 'SLOs', icon: AlertCircle },
      { to: '/fleets', label: 'Fleets', icon: Layers },
      { to: '/audit', label: 'Audit', icon: ClipboardList },
    ],
  },
  {
    id: 'ai',
    label: 'AI Features',
    items: [
      { to: '/ai-insights', label: 'AI Insights', icon: BrainCircuit },
      { to: '/ai-risk', label: 'AI Risk', icon: Gauge },
      { to: '/ai-functions', label: 'AI Functions', icon: Code2 },
    ],
  },
]

export default function Layout() {
  const auth = useAuth()
  const location = useLocation()

  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    core: true,
    operations: true,
    ai: true,
  })

  const activeSectionIds = useMemo(() => {
    return NAV_SECTIONS
      .filter((section) =>
        section.items.some((item) =>
          location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
        )
      )
      .map((section) => section.id)
  }, [location.pathname])

  useEffect(() => {
    if (activeSectionIds.length === 0) return
    setOpenSections((prev) => {
      const next = { ...prev }
      let changed = false
      for (const sectionId of activeSectionIds) {
        if (!next[sectionId]) {
          next[sectionId] = true
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [activeSectionIds])

  function toggleSection(sectionId: string) {
    setOpenSections((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }))
  }

  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-slate-800 flex flex-col">
        <div className="px-4 py-4 border-b border-slate-700">
          <div className="text-white font-semibold text-base tracking-tight">Nexora</div>
          <div className="text-slate-400 text-xs mt-0.5">IoT Platform</div>
        </div>

        <nav className="flex-1 py-3">
          {NAV_SECTIONS.map((section) => {
            const isOpen = openSections[section.id]
            const hasActiveItem = activeSectionIds.includes(section.id)
            return (
              <div key={section.id} className="mb-2">
                <button
                  onClick={() => toggleSection(section.id)}
                  className={`w-full flex items-center justify-between px-4 py-2 text-xs uppercase tracking-wide transition-colors ${
                    hasActiveItem ? 'text-cyan-300' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span>{section.label}</span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
                  />
                </button>

                {isOpen && (
                  <div className="space-y-0.5">
                    {section.items.map(({ to, label, icon: Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                          `mx-2 flex items-center gap-2.5 rounded px-3 py-2 text-sm transition-colors ${
                            isActive
                              ? 'bg-blue-600 text-white font-medium'
                              : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                          }`
                        }
                      >
                        <Icon size={15} />
                        {label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        <div className="px-4 py-3 border-t border-slate-700">
          {auth.user && (
            <div className="mb-3">
              <div className="truncate text-xs font-medium text-slate-200">{auth.user.name}</div>
              <div className="truncate text-xs text-slate-400">{auth.user.tenantId}</div>
            </div>
          )}
          {auth.authenticated && (
            <button
              onClick={auth.logout}
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-white"
            >
              <LogOut size={13} />
              Sign out
            </button>
          )}
          <div className="text-slate-500 text-xs">v0.3.0</div>
        </div>
      </aside>

      {/* Page content */}
      <main className="flex-1 bg-slate-50 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
