import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'
import StatusBadge from '../components/StatusBadge'

export default function Fleets() {
  const { data: fleets, loading: loadingFleets } = useApi(() => api.listFleets())
  const [selectedId, setSelectedId] = useState('')

  const { data: health, loading: loadingHealth, reload } = useApi(
    () => selectedId ? api.getFleetHealth(selectedId) : Promise.resolve(null),
    [selectedId]
  )

  const summaryData = health
    ? [
        { name: 'Online',  value: health.summary.online,  fill: '#34d399' },
        { name: 'Offline', value: health.summary.offline, fill: '#f87171' },
        { name: 'Unknown', value: health.summary.unknown, fill: '#6b7280' },
      ]
    : []

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Fleets</h1>
        <button
          onClick={reload}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm text-gray-300"
        >
          <RefreshCw size={14} className={loadingHealth ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="flex gap-6">
        {/* Fleet list sidebar */}
        <div className="w-56 shrink-0 space-y-1">
          {loadingFleets ? (
            <p className="text-gray-600 text-sm text-center py-4">Loading…</p>
          ) : !fleets?.items.length ? (
            <p className="text-gray-600 text-sm text-center py-4">No fleets</p>
          ) : fleets.items.map(f => (
            <button
              key={f.id}
              onClick={() => setSelectedId(f.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
                selectedId === f.id
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <div className="font-medium truncate">{f.name}</div>
              {f.description && (
                <div className="text-xs opacity-60 truncate mt-0.5">{f.description}</div>
              )}
            </button>
          ))}
        </div>

        {/* Fleet detail */}
        <div className="flex-1">
          {!selectedId ? (
            <div className="rounded-xl border border-gray-800 bg-gray-900/30 py-16 text-center text-gray-600">
              Select a fleet to view health
            </div>
          ) : loadingHealth ? (
            <div className="text-gray-500 text-sm py-8 text-center">Loading…</div>
          ) : health ? (
            <>
              <h2 className="text-lg font-semibold text-white mb-4">{health.fleet_name}</h2>

              {/* Summary cards */}
              <div className="grid grid-cols-4 gap-3 mb-6">
                {[
                  { label: 'Total', value: health.summary.total, color: 'text-white' },
                  { label: 'Online', value: health.summary.online, color: 'text-green-400' },
                  { label: 'Offline', value: health.summary.offline, color: 'text-red-400' },
                  { label: 'Unknown', value: health.summary.unknown, color: 'text-gray-400' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-center">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Bar chart */}
              {health.summary.total > 0 && (
                <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 mb-6">
                  <ResponsiveContainer width="100%" height={140}>
                    <BarChart data={summaryData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                      />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {summaryData.map((entry, i) => (
                          <Cell key={i} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Device list */}
              <div className="rounded-xl border border-gray-800 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900/50">
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Device</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50">
                    {health.devices.map(d => (
                      <tr key={d.device_id} className="hover:bg-gray-800/30 transition-colors">
                        <td className="px-4 py-3 font-medium text-white">{d.name ?? d.device_id.slice(0, 8)}</td>
                        <td className="px-4 py-3 text-gray-400">{d.device_type ?? '—'}</td>
                        <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {d.last_seen ? new Date(d.last_seen).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
