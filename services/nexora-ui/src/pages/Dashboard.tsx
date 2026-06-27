import { Activity, Cpu, RadioTower, Zap } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'

const DEVICE_COLORS: Record<string, string> = {
  online: '#10b981',
  offline: '#f59e0b',
  unknown: '#64748b',
}

const EXEC_COLORS: Record<string, string> = {
  succeeded: '#10b981',
  failed: '#ef4444',
  running: '#3b82f6',
  queued: '#f59e0b',
  dispatched: '#8b5cf6',
  cancelled: '#64748b',
}

export default function Dashboard() {
  const { data, loading, error, reload } = useApi(async () => {
    const [devicesResp, pendingResp, executionsResp] = await Promise.all([
      api.listDevices(1, 200),
      api.listPendingDevices(),
      api.listExecutions(1, 200),
    ])
    return {
      devices: devicesResp.items,
      pending: pendingResp,
      executions: executionsResp.items,
    }
  }, [])

  const devices = data?.devices ?? []
  const pending = data?.pending ?? []
  const executions = data?.executions ?? []

  const deviceStatusRows = ['online', 'offline', 'unknown'].map((status) => ({
    status,
    count: devices.filter((d) => d.status === status).length,
    fill: DEVICE_COLORS[status],
  }))

  const executionStatusRows = Object.entries(
    executions.reduce<Record<string, number>>((acc, item) => {
      const key = (item.status || 'unknown').toLowerCase()
      acc[key] = (acc[key] ?? 0) + 1
      return acc
    }, {})
  )
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)

  const onlineCount = deviceStatusRows.find((r) => r.status === 'online')?.count ?? 0
  const offlineCount = deviceStatusRows.find((r) => r.status === 'offline')?.count ?? 0

  return (
    <div className="p-6 space-y-6">
      <section className="rounded-2xl border border-cyan-100 bg-gradient-to-r from-cyan-50 via-sky-50 to-indigo-50 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-700">Nexora Control</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-900">Operational Dashboard</h1>
            <p className="mt-1 text-sm text-slate-600">Live visibility on fleet health, pairing queue, and execution flow.</p>
          </div>
          <button
            onClick={reload}
            className="rounded-lg border border-cyan-200 bg-white/80 px-3 py-1.5 text-sm text-cyan-800 hover:bg-white"
          >
            Refresh Data
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Registered Devices" value={String(devices.length)} hint="Total inventory" icon={<Cpu size={16} />} tone="cyan" />
        <StatCard title="Online Now" value={String(onlineCount)} hint={`${offlineCount} offline`} icon={<RadioTower size={16} />} tone="emerald" />
        <StatCard title="Pending Pairings" value={String(pending.length)} hint="Waiting owner approval" icon={<Zap size={16} />} tone="amber" />
        <StatCard title="Executions" value={String(executions.length)} hint="Latest 200 jobs" icon={<Activity size={16} />} tone="violet" />
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">Device Status Mix</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={deviceStatusRows} dataKey="count" nameKey="status" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {deviceStatusRows.map((entry) => (
                    <Cell key={entry.status} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="xl:col-span-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">Execution Status</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={executionStatusRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="status" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {executionStatusRows.map((row) => (
                    <Cell key={row.status} fill={EXEC_COLORS[row.status] ?? '#0ea5e9'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-800">Pending Pairing Queue</h2>
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : pending.length === 0 ? (
          <p className="text-sm text-slate-500">No devices waiting for pairing.</p>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-2 py-2">Hardware ID</th>
                  <th className="px-2 py-2">Type</th>
                  <th className="px-2 py-2">User Code</th>
                  <th className="px-2 py-2">Announced</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((item) => (
                  <tr key={item.discovery_id} className="border-b border-slate-100 text-slate-700">
                    <td className="px-2 py-2 font-mono text-xs">{item.hardware_id}</td>
                    <td className="px-2 py-2">{item.device_type}</td>
                    <td className="px-2 py-2 font-semibold">{item.user_code}</td>
                    <td className="px-2 py-2 text-xs">{new Date(item.announced_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function StatCard({
  title,
  value,
  hint,
  icon,
  tone,
}: {
  title: string
  value: string
  hint: string
  icon: React.ReactNode
  tone: 'cyan' | 'emerald' | 'amber' | 'violet'
}) {
  const tones: Record<string, string> = {
    cyan: 'border-cyan-200 bg-cyan-50 text-cyan-900',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    violet: 'border-violet-200 bg-violet-50 text-violet-900',
  }

  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide">{title}</p>
        <span>{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs opacity-80">{hint}</p>
    </div>
  )
}
