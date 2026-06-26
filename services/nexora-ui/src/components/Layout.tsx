import { NavLink, Outlet } from 'react-router-dom'
import { Cpu, BarChart2, AlertTriangle, Layers } from 'lucide-react'

const NAV = [
  { to: '/devices', label: 'Devices',    icon: Cpu },
  { to: '/telemetry', label: 'Telemetry', icon: BarChart2 },
  { to: '/slo',      label: 'SLO',        icon: AlertTriangle },
  { to: '/fleets',   label: 'Fleets',     icon: Layers },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-800">
          <span className="text-lg font-bold tracking-tight text-white">Nexora</span>
          <span className="ml-1 text-xs text-purple-400 font-medium">Platform</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-purple-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-gray-800 text-xs text-gray-600">
          v0.2.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
