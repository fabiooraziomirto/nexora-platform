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
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      <aside className="hidden h-full w-[220px] shrink-0 flex-col overflow-y-auto border-r border-white/5 bg-[#0d1117] text-white lg:flex">
        <div className="shrink-0 border-b border-white/[0.06] px-3.5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg bg-indigo-600">
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <circle cx="9" cy="9" r="7" fill="none" stroke="rgba(255,255,255,.9)" strokeWidth="1.5" />
                <circle cx="9" cy="9" r="2.5" fill="white" />
                <circle cx="9" cy="2" r="1.8" fill="#2dd4bf" />
                <circle cx="15.1" cy="12.5" r="1.8" fill="#2dd4bf" />
                <circle cx="2.9" cy="12.5" r="1.8" fill="#2dd4bf" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-bold leading-tight tracking-normal text-white">nexora</div>
              <div className="text-[10px] text-white/35">IoT Platform</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {NAV_SECTIONS.map((section) => {
            const isOpen = openSections[section.id]
            const hasActiveItem = activeSectionIds.includes(section.id)
            return (
              <div key={section.id} className="mb-1">
                <button
                  onClick={() => toggleSection(section.id)}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[9px] font-bold uppercase tracking-[0.14em] transition-colors ${
                    hasActiveItem
                      ? 'text-indigo-200'
                      : 'text-white/25 hover:bg-white/[0.04] hover:text-white/50'
                  }`}
                >
                  <span>{section.label}</span>
                  <ChevronDown
                    size={12}
                    className={`transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
                  />
                </button>

                {isOpen && (
                  <div className="space-y-px">
                    {section.items.map(({ to, label, icon: Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                          `group relative flex items-center gap-2 rounded-[7px] px-2 py-1.5 text-[12.5px] transition-all ${
                            isActive
                              ? 'bg-indigo-500/20 font-medium text-indigo-200 before:absolute before:left-0 before:top-[18%] before:h-[64%] before:w-[2.5px] before:rounded-full before:bg-indigo-300'
                              : 'text-white/50 hover:bg-white/[0.06] hover:text-white/85'
                          }`
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <span className={`inline-flex h-[26px] w-[26px] items-center justify-center rounded-md transition-colors ${isActive ? 'bg-indigo-500/30 text-indigo-200' : 'bg-white/[0.05] text-white/45 group-hover:bg-white/[0.09] group-hover:text-white/85'}`}>
                              <Icon size={13} />
                            </span>
                            <span>{label}</span>
                          </>
                        )}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        <div className="shrink-0 border-t border-white/[0.06] px-3.5 py-3">
          {auth.user && (
            <div className="mb-2 rounded-[9px] border border-white/10 bg-white/[0.04] px-3 py-2.5">
              <div className="truncate text-xs font-semibold text-white/90">{auth.user.name}</div>
              <div className="truncate text-[10px] text-white/35">{auth.user.tenantId}</div>
            </div>
          )}
          {auth.authenticated && (
            <button
              onClick={auth.logout}
              className="mb-1.5 inline-flex items-center gap-1.5 rounded px-1 py-1 text-[11px] text-white/35 transition-colors hover:bg-white/[0.06] hover:text-white/65"
            >
              <LogOut size={11} />
              Sign out
            </button>
          )}
          <div className="text-[10px] text-white/20">Nexora v0.3.0</div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-slate-50">
        <Outlet />
      </main>
    </div>
  )
}
