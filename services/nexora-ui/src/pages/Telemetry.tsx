import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BarChart2 } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'
import { SkeletonCard } from '../components/Skeleton'

const COLORS = ['#2563eb', '#16a34a', '#ea580c', '#0891b2', '#9333ea', '#ca8a04']
const HOUR_OPTIONS = [1, 6, 24, 48, 168]

const SELECT = 'border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

export default function Telemetry() {
  const [params] = useSearchParams()
  const [deviceId, setDeviceId] = useState(params.get('device') ?? '')
  const [metric, setMetric]     = useState('')
  const [hours, setHours]       = useState(24)

  const { data: devices } = useApi(() => api.listDevices(1, 200))
  const { data: latest, loading: loadingLatest } = useApi(
    () => deviceId ? api.getLatestTelemetry(deviceId) : Promise.resolve(null),
    [deviceId]
  )
  const { data: history, loading: loadingHistory, error } = useApi(
    () => deviceId ? api.getTelemetry(deviceId, metric || undefined, hours) : Promise.resolve(null),
    [deviceId, metric, hours]
  )

  const metrics = latest ? Object.keys(latest.readings) : []
  const selectedMetrics = metric ? [metric] : metrics.slice(0, 6)

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
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Telemetry</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {deviceId && latest ? `${metrics.length} metric${metrics.length !== 1 ? 's' : ''}` : 'Select a device'}
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 mb-5">
        <select className={SELECT} value={deviceId} onChange={e => { setDeviceId(e.target.value); setMetric('') }}>
          <option value="">Select device…</option>
          {devices?.items.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        {metrics.length > 0 && (
          <select className={SELECT} value={metric} onChange={e => setMetric(e.target.value)}>
            <option value="">All metrics</option>
            {metrics.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        )}

        <select className={SELECT} value={hours} onChange={e => setHours(Number(e.target.value))}>
          {HOUR_OPTIONS.map(h => <option key={h} value={h}>Last {h}h</option>)}
        </select>
      </div>

      {!deviceId ? (
        <div className="bg-white border border-slate-200 rounded py-20 flex flex-col items-center text-slate-400">
          <BarChart2 size={36} className="mb-3 opacity-25" />
          <p className="text-sm font-medium">Select a device to view telemetry</p>
        </div>
      ) : (
        <>
          {/* Latest readings */}
          {loadingLatest ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
              {[1,2,3,4].map(i => <SkeletonCard key={i} />)}
            </div>
          ) : latest && metrics.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
              {Object.entries(latest.readings).map(([m, r], i) => (
                <button
                  key={m}
                  onClick={() => setMetric(metric === m ? '' : m)}
                  className={`text-left rounded border p-3.5 transition-colors ${
                    metric === m
                      ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-300'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <p className="text-xs text-slate-500 font-medium truncate">{m}</p>
                  <p className="text-2xl font-bold mt-1 tabular-nums" style={{ color: COLORS[i % COLORS.length] }}>
                    {r.value.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {new Date(r.ts).toLocaleTimeString()}
                  </p>
                </button>
              ))}
            </div>
          ) : null}

          {error && (
            <div className="rounded border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-2.5 mb-4">
              {error}
            </div>
          )}

          {/* Chart */}
          {loadingHistory ? (
            <div className="bg-white border border-slate-200 rounded p-4">
              <div className="h-72 flex items-center justify-center">
                <div className="text-slate-300 text-sm">Loading…</div>
              </div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded py-16 text-center text-slate-400 text-sm">
              No data for the selected time window
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded p-4">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="ts" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 4, fontSize: 12 }}
                    labelStyle={{ color: '#475569' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#64748b' }} />
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
        </>
      )}
    </div>
  )
}
