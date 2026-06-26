import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Search } from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'
import StatusBadge from '../components/StatusBadge'

export default function Devices() {
  const { data, loading, error, reload } = useApi(() => api.listDevices(1, 100))
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const devices = data?.items.filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.device_type.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Devices</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data ? `${data.total} total` : '—'}
          </p>
        </div>
        <button
          onClick={reload}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm text-gray-300 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          className="w-full max-w-sm bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
          placeholder="Filter by name or type…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="text-gray-500 text-sm py-8 text-center">Loading…</div>
      ) : (
        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {devices.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-600">
                    No devices found
                  </td>
                </tr>
              ) : devices.map(d => (
                <tr
                  key={d.id}
                  onClick={() => navigate(`/telemetry?device=${d.id}`)}
                  className="hover:bg-gray-800/40 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-white">{d.name}</td>
                  <td className="px-4 py-3 text-gray-400">{d.device_type}</td>
                  <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {d.last_seen ? new Date(d.last_seen).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
