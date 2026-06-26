import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'

const COLORS = ['#a78bfa', '#34d399', '#fb923c', '#38bdf8', '#f472b6', '#facc15']
const HOUR_OPTIONS = [1, 6, 24, 48, 168]

export default function Telemetry() {
  const [params] = useSearchParams()
  const [deviceId, setDeviceId] = useState(params.get('device') ?? '')
  const [metric, setMetric] = useState('')
  const [hours, setHours] = useState(24)

  const { data: devices } = useApi(() => api.listDevices(1, 200))
  const { data: latest } = useApi(
    () => deviceId ? api.getLatestTelemetry(deviceId) : Promise.resolve(null),
    [deviceId]
  )
  const { data: history, loading, error } = useApi(
    () => deviceId ? api.getTelemetry(deviceId, metric || undefined, hours) : Promise.resolve(null),
    [deviceId, metric, hours]
  )

  const metrics = latest ? Object.keys(latest.readings) : []
  const selectedMetrics = metric ? [metric] : metrics.slice(0, 4)

  // Build chart series: one entry per timestamp, each metric a key
  const byTs: Record<string, Record<string, number>> = {}
  if (history?.samples) {
    for (const s of history.samples) {
      if (!byTs[s.ts]) byTs[s.ts] = {}
      byTs[s.ts][s.metric] = s.value
    }
  }
  const chartData = Object.entries(byTs)
    .map(([ts, vals]) => ({ ts: new Date(ts).toLocaleTimeString(), ...vals }))
    .reverse()

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Telemetry</h1>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
          value={deviceId}
          onChange={e => { setDeviceId(e.target.value); setMetric('') }}
        >
          <option value="">Select device…</option>
          {devices?.items.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        {metrics.length > 0 && (
          <select
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
            value={metric}
            onChange={e => setMetric(e.target.value)}
          >
            <option value="">All metrics</option>
            {metrics.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        )}

        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
          value={hours}
          onChange={e => setHours(Number(e.target.value))}
        >
          {HOUR_OPTIONS.map(h => <option key={h} value={h}>Last {h}h</option>)}
        </select>
      </div>

      {/* Latest readings */}
      {latest && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-6">
          {Object.entries(latest.readings).map(([m, r], i) => (
            <div
              key={m}
              onClick={() => setMetric(metric === m ? '' : m)}
              className={`rounded-xl border p-4 cursor-pointer transition-colors ${
                metric === m
                  ? 'border-purple-500 bg-purple-500/10'
                  : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}
            >
              <p className="text-xs text-gray-500 truncate">{m}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: COLORS[i % COLORS.length] }}>
                {r.value.toFixed(2)}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                {new Date(r.ts).toLocaleTimeString()}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {/* Chart */}
      {!deviceId ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900/30 py-16 text-center text-gray-600">
          Select a device to view telemetry
        </div>
      ) : loading ? (
        <div className="text-gray-500 text-sm py-8 text-center">Loading…</div>
      ) : chartData.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900/30 py-16 text-center text-gray-600">
          No data for the selected window
        </div>
      ) : (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="ts" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {selectedMetrics.map((m, i) => (
                <Line
                  key={m}
                  type="monotone"
                  dataKey={m}
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
