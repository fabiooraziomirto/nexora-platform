import { Activity, AlertTriangle, Cpu, FileClock, RefreshCw, RadioTower } from 'lucide-react'
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
  const latestExecutions = executions.slice(0, 6)
  const offlineCopy = offlineCount === 1 ? '1 device offline' : `${offlineCount} devices offline`

  return (
    <div>
      <div className="mb-5 flex items-start justify-between gap-4 px-6 pt-5">
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-indigo-500">Nexora Control</div>
          <h1 className="text-xl font-bold leading-tight tracking-normal text-slate-900">Operational Dashboard</h1>
          <p className="mt-1 text-xs text-slate-500">Live visibility on fleet health, pairing queue, and execution flow</p>
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-1">
          <span className="hidden text-[11px] text-slate-400 sm:inline">Updated just now</span>
          <button
            onClick={reload}
            className="inline-flex items-center gap-1.5 rounded-[7px] border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="px-6 pb-6">
        {error && (
          <div className="mb-4 flex items-start gap-3 rounded-[9px] border border-red-500/15 border-l-[3.5px] border-l-red-500 bg-red-50 px-4 py-3 text-xs text-red-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-500" />
            <div className="flex-1 leading-6">{error}</div>
            <span className="rounded-full bg-red-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-red-700">Error</span>
          </div>
        )}

        {offlineCount > 0 && (
          <div className="mb-5 flex items-start gap-3 rounded-[9px] border border-red-500/15 border-l-[3.5px] border-l-red-500 bg-red-50 px-4 py-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-500" />
            <div className="flex-1 text-xs leading-6 text-red-900">
              <b className="font-semibold text-red-700">{offlineCopy}</b> - Check network connectivity or device power status.
            </div>
            <span className="rounded-full bg-red-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-red-700">Critical</span>
          </div>
        )}

        <section className="mb-5 grid gap-3.5 md:grid-cols-2 xl:grid-cols-4">
          <StatCard title="Registered Devices" value={String(devices.length)} hint="Total inventory" icon={<Cpu size={13} />} tone="indigo" trend="+2 this week" />
          <StatCard title="Online Now" value={String(onlineCount)} hint={`${offlineCount} of ${devices.length} offline`} icon={<RadioTower size={13} />} tone={onlineCount > 0 ? 'teal' : 'red'} trend={onlineCount > 0 ? 'Live fleet reachable' : 'All devices offline'} />
          <StatCard title="Pending Pairings" value={String(pending.length)} hint="Awaiting owner approval" icon={<FileClock size={13} />} tone="amber" trend={pending.length > 0 ? 'Review queue' : 'Queue empty'} />
          <StatCard title="Executions" value={String(executions.length)} hint="Latest 200 jobs" icon={<Activity size={13} />} tone="teal" trend="Dispatch flow" />
        </section>

        <section className="mb-5 grid gap-3.5 xl:grid-cols-[264px_1fr]">
          <div className="rounded-[10px] border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3.5">
              <h2 className="text-xs font-semibold text-slate-800">Device Status Mix</h2>
              <p className="text-[10px] text-slate-400">Current fleet reachability</p>
            </div>
            <div className="relative h-[148px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={deviceStatusRows} dataKey="count" nameKey="status" innerRadius={48} outerRadius={70} paddingAngle={2}>
                    {deviceStatusRows.map((entry) => (
                      <Cell key={entry.status} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <div className="font-mono text-2xl font-bold leading-none text-slate-900">{devices.length}</div>
                <div className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">devices</div>
              </div>
            </div>
            <div className="mt-3.5 space-y-2">
              {deviceStatusRows.map((row) => (
                <div key={row.status} className="flex items-center justify-between text-[11px] text-slate-600">
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-sm" style={{ background: row.fill }} />
                    {row.status}
                  </span>
                  <span className="font-mono font-medium text-slate-900">{row.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[10px] border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3.5 flex items-center justify-between">
              <div>
                <h2 className="text-xs font-semibold text-slate-800">Execution Status</h2>
                <p className="text-[10px] text-slate-400">Latest job outcomes by state</p>
              </div>
              <span className="text-[11px] text-slate-500">{executions.length} sampled</span>
            </div>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={executionStatusRows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="status" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {executionStatusRows.map((row) => (
                      <Cell key={row.status} fill={EXEC_COLORS[row.status] ?? '#6366f1'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        <section className="grid gap-3.5 xl:grid-cols-[264px_1fr]">
          <Panel title="Pending Pairing Queue" subtitle="Devices awaiting owner approval" badge={`${pending.length}`}>
            {loading ? (
              <EmptyState text="Loading..." />
            ) : pending.length === 0 ? (
              <EmptyState text="No devices waiting for pairing." />
            ) : (
              <div className="overflow-auto">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <TableHead>Hardware ID</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>User Code</TableHead>
                    </tr>
                  </thead>
                  <tbody>
                    {pending.slice(0, 5).map((item) => (
                      <tr key={item.discovery_id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                        <TableCell mono>{item.hardware_id}</TableCell>
                        <TableCell>{item.device_type}</TableCell>
                        <TableCell strong>{item.user_code}</TableCell>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title="Recent Executions" subtitle="Most recent dispatch activity" badge={`${latestExecutions.length}`}>
            {loading ? (
              <EmptyState text="Loading..." />
            ) : latestExecutions.length === 0 ? (
              <EmptyState text="No executions recorded yet." />
            ) : (
              <div className="overflow-auto">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <TableHead>Execution</TableHead>
                      <TableHead>Command</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </tr>
                  </thead>
                  <tbody>
                    {latestExecutions.map((item) => (
                      <tr key={item.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                        <TableCell mono>{item.id}</TableCell>
                        <TableCell>{item.command || 'n/a'}</TableCell>
                        <TableCell><StatusPill status={item.status ?? 'unknown'} /></TableCell>
                        <TableCell>{item.created_at ? new Date(item.created_at).toLocaleString() : 'n/a'}</TableCell>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </section>
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  hint,
  icon,
  tone,
  trend,
}: {
  title: string
  value: string
  hint: string
  icon: React.ReactNode
  tone: 'indigo' | 'red' | 'amber' | 'teal'
  trend: string
}) {
  const tones = {
    indigo: { border: 'border-t-indigo-500', icon: 'bg-indigo-500/10 text-indigo-500', trend: 'text-emerald-600' },
    red: { border: 'border-t-red-500', icon: 'bg-red-500/10 text-red-500', trend: 'text-red-500' },
    amber: { border: 'border-t-amber-500', icon: 'bg-amber-500/10 text-amber-600', trend: 'text-slate-400' },
    teal: { border: 'border-t-teal-500', icon: 'bg-teal-500/10 text-teal-500', trend: 'text-emerald-600' },
  }[tone]

  return (
    <div className={`rounded-[10px] border border-slate-200 border-t-[2.5px] ${tones.border} bg-white px-4 py-4 shadow-sm`}>
      <div className="mb-2.5 flex items-start justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">{title}</span>
        <span className={`flex h-7 w-7 items-center justify-center rounded-[7px] ${tones.icon}`}>{icon}</span>
      </div>
      <div className={`font-mono text-[28px] font-bold leading-none tracking-normal ${tone === 'red' ? 'text-red-600' : 'text-slate-900'}`}>{value}</div>
      <div className="mt-1 text-[11px] text-slate-500">{hint}</div>
      <div className={`mt-3.5 text-[10px] font-semibold ${tones.trend}`}>{trend}</div>
    </div>
  )
}

function Panel({ title, subtitle, badge, children }: { title: string; subtitle: string; badge: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[10px] border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5">
        <div>
          <h2 className="text-xs font-semibold text-slate-800">{title}</h2>
          <p className="mt-px text-[10px] text-slate-400">{subtitle}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-500">{badge}</span>
      </div>
      {children}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="px-5 py-7 text-center text-xs text-slate-400">
      {text}
    </div>
  )
}

function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <th className="whitespace-nowrap border-b border-slate-100 bg-slate-50 px-3.5 py-2.5 text-[10px] font-semibold uppercase tracking-[0.07em] text-slate-400">
      {children}
    </th>
  )
}

function TableCell({ children, mono, strong }: { children: React.ReactNode; mono?: boolean; strong?: boolean }) {
  return (
    <td className={`px-3.5 py-2.5 text-xs text-slate-700 ${mono ? 'font-mono text-[11px]' : ''} ${strong ? 'font-semibold text-slate-900' : ''}`}>
      {children}
    </td>
  )
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    succeeded: 'bg-emerald-50 text-emerald-700',
    failed: 'bg-red-50 text-red-700',
    running: 'bg-blue-50 text-blue-700',
    queued: 'bg-amber-50 text-amber-700',
    dispatched: 'bg-violet-50 text-violet-700',
    cancelled: 'bg-slate-100 text-slate-500',
  }

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ${styles[status] ?? 'bg-slate-100 text-slate-500'}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-75" />
      {status}
    </span>
  )
}
