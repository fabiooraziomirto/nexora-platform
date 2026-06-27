import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ChevronDown, LayoutDashboard, Monitor, BarChart2, AlertCircle, Layers, Package, Terminal, Network, Globe, BrainCircuit, Gauge, Code2, ClipboardList, Wand2, LogOut, Sparkles } from 'lucide-react'
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
      <aside className="relative w-64 shrink-0 overflow-hidden border-r border-slate-800/80 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col">
        <div className="pointer-events-none absolute -top-20 -left-16 h-40 w-40 rounded-full bg-cyan-500/20 blur-3xl" />
        <div className="pointer-events-none absolute top-1/3 -right-16 h-44 w-44 rounded-full bg-indigo-500/20 blur-3xl" />

        <div className="relative px-4 py-5 border-b border-slate-800/90">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200">
            <Sparkles size={11} />
            Control Plane
          </div>
          <img
            src="/nexora-logo-reversed.svg"
            alt="Nexora"
            className="mt-3 h-6 w-auto"
          />
          <div className="text-slate-300/80 text-xs mt-1">Edge orchestration platform</div>
        </div>

        <nav className="relative flex-1 py-3">
          {NAV_SECTIONS.map((section) => {
            const isOpen = openSections[section.id]
            const hasActiveItem = activeSectionIds.includes(section.id)
            return (
              <div key={section.id} className="mb-2">
                <button
                  onClick={() => toggleSection(section.id)}
                  className={`mx-2 w-[calc(100%-1rem)] flex items-center justify-between rounded-lg px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors ${
                    hasActiveItem
                      ? 'bg-slate-800/80 text-cyan-200'
                      : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
                  }`}
                >
                  <span>{section.label}</span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
                  />
                </button>

                {isOpen && (
                  <div className="mt-1 space-y-1 px-2">
                    {section.items.map(({ to, label, icon: Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                          `group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-all ${
                            isActive
                              ? 'bg-gradient-to-r from-cyan-500/90 to-blue-500/90 text-white font-medium shadow-[0_8px_24px_-12px_rgba(6,182,212,0.95)]'
                              : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                          }`
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <span className={`inline-flex h-6 w-6 items-center justify-center rounded-md ${isActive ? 'bg-white/20 text-white' : 'bg-slate-700/70 text-slate-200 group-hover:bg-slate-700 group-hover:text-white'}`}>
                              <Icon size={14} />
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

        <div className="relative px-4 py-3 border-t border-slate-800/90">
          {auth.user && (
            <div className="mb-3 rounded-xl border border-slate-700/80 bg-slate-800/65 px-3 py-2">
              <div className="truncate text-xs font-semibold text-slate-100">{auth.user.name}</div>
              <div className="truncate text-xs text-slate-400">{auth.user.tenantId}</div>
            </div>
          )}
          {auth.authenticated && (
            <button
              onClick={auth.logout}
              className="mb-3 inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
            >
              <LogOut size={13} />
              Sign out
            </button>
          )}
          <div className="text-slate-500 text-xs">Nexora v0.3.0</div>
        </div>
      </aside>

      {/* Page content */}
      <main className="flex-1 bg-slate-50 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
