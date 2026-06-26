import { NavLink, Outlet } from 'react-router-dom'
import { Monitor, BarChart2, AlertCircle, Layers, Package, Terminal, Network, Globe } from 'lucide-react'

const NAV = [
  { to: '/devices',     label: 'Devices',     icon: Monitor },
  { to: '/plugins',     label: 'Plugins',     icon: Package },
  { to: '/executions',  label: 'Executions',  icon: Terminal },
  { to: '/ports',       label: 'Ports',       icon: Network },
  { to: '/webservices', label: 'Webservices', icon: Globe },
  { to: '/telemetry',   label: 'Telemetry',   icon: BarChart2 },
  { to: '/slo',         label: 'SLOs',        icon: AlertCircle },
  { to: '/fleets',      label: 'Fleets',      icon: Layers },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 bg-slate-800 flex flex-col">
        <div className="px-4 py-4 border-b border-slate-700">
          <div className="text-white font-semibold text-base tracking-tight">Nexora</div>
          <div className="text-slate-400 text-xs mt-0.5">IoT Platform</div>
        </div>

        <nav className="flex-1 py-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
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
        </nav>

        <div className="px-4 py-3 border-t border-slate-700 text-slate-500 text-xs">
          v0.3.0
        </div>
      </aside>

      {/* Page content */}
      <main className="flex-1 bg-slate-50 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
