import { useState } from 'react'
import { AlertTriangle, Plus, Trash2, RefreshCw } from 'lucide-react'
import { api, type SLO as SLOType } from '../api/client'
import { useApi } from '../hooks/useApi'

const OPERATORS = ['lt', 'lte', 'gt', 'gte', 'eq']
const OP_LABEL: Record<string, string> = { lt: '<', lte: '≤', gt: '>', gte: '≥', eq: '=' }

function ViolationRow({ v }: { v: { metric: string; observed_value: number; threshold: number; operator: string; violated_at: string } }) {
  return (
    <tr className="hover:bg-gray-800/30 transition-colors">
      <td className="px-4 py-2.5 text-gray-300 font-mono text-sm">{v.metric}</td>
      <td className="px-4 py-2.5 text-red-400 font-mono text-sm">
        {v.observed_value.toFixed(3)} {OP_LABEL[v.operator]} {v.threshold}
      </td>
      <td className="px-4 py-2.5 text-gray-500 text-xs">
        {new Date(v.violated_at).toLocaleString()}
      </td>
    </tr>
  )
}

export default function SLO() {
  const { data: devices } = useApi(() => api.listDevices(1, 200))
  const [deviceId, setDeviceId] = useState('')
  const [hours, setHours] = useState(24)

  const { data: slos, reload: reloadSLOs } = useApi(
    () => deviceId ? api.listSLOs(deviceId) : Promise.resolve([] as SLOType[]),
    [deviceId]
  )
  const { data: violations, reload: reloadViolations } = useApi(
    () => deviceId ? api.listViolations(deviceId, hours) : Promise.resolve([]),
    [deviceId, hours]
  )

  // New SLO form
  const [form, setForm] = useState({ metric: '', operator: 'lt', threshold: '' })
  const [adding, setAdding] = useState(false)

  async function handleCreate() {
    if (!deviceId || !form.metric || !form.threshold) return
    await api.createSLO(deviceId, {
      metric: form.metric,
      operator: form.operator,
      threshold: parseFloat(form.threshold),
    })
    setForm({ metric: '', operator: 'lt', threshold: '' })
    setAdding(false)
    reloadSLOs()
  }

  async function handleDelete(sloId: string) {
    await api.deleteSLO(deviceId, sloId)
    reloadSLOs()
  }

  const reload = () => { reloadSLOs(); reloadViolations() }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">SLO & Violations</h1>
        <button
          onClick={reload}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm text-gray-300"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Device picker */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
          value={deviceId}
          onChange={e => setDeviceId(e.target.value)}
        >
          <option value="">Select device…</option>
          {devices?.items.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
          value={hours}
          onChange={e => setHours(Number(e.target.value))}
        >
          {[1, 6, 24, 48, 168].map(h => <option key={h} value={h}>Violations: last {h}h</option>)}
        </select>
      </div>

      {!deviceId ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900/30 py-16 text-center text-gray-600">
          Select a device to manage SLOs
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* SLO definitions */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Defined SLOs</h2>
              <button
                onClick={() => setAdding(v => !v)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs text-white"
              >
                <Plus size={12} /> New SLO
              </button>
            </div>

            {/* Add form */}
            {adding && (
              <div className="rounded-xl border border-purple-500/40 bg-purple-500/5 p-4 mb-3 space-y-3">
                <input
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  placeholder="Metric (e.g. temperature)"
                  value={form.metric}
                  onChange={e => setForm(f => ({ ...f, metric: e.target.value }))}
                />
                <div className="flex gap-2">
                  <select
                    className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                    value={form.operator}
                    onChange={e => setForm(f => ({ ...f, operator: e.target.value }))}
                  >
                    {OPERATORS.map(op => <option key={op} value={op}>{OP_LABEL[op]} ({op})</option>)}
                  </select>
                  <input
                    type="number"
                    className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                    placeholder="Threshold"
                    value={form.threshold}
                    onChange={e => setForm(f => ({ ...f, threshold: e.target.value }))}
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setAdding(false)} className="px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200">Cancel</button>
                  <button onClick={handleCreate} className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs text-white">Save</button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {!slos || slos.length === 0 ? (
                <p className="text-gray-600 text-sm py-4 text-center">No SLOs defined</p>
              ) : slos.map(s => (
                <div key={s.id} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900/50 px-4 py-3">
                  <div>
                    <span className="text-sm font-medium text-white">{s.metric}</span>
                    <span className="ml-2 text-sm text-gray-400">
                      {OP_LABEL[s.operator]} {s.threshold}
                    </span>
                    {!s.enabled && (
                      <span className="ml-2 text-xs text-gray-600 italic">disabled</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Violations */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={14} className="text-amber-400" />
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                Recent Violations
                {violations && violations.length > 0 && (
                  <span className="ml-2 inline-flex items-center justify-center rounded-full bg-red-500/20 text-red-400 text-xs px-1.5 py-0.5">
                    {violations.length}
                  </span>
                )}
              </h2>
            </div>
            <div className="rounded-xl border border-gray-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-900/50">
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">Metric</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">Value</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {!violations || violations.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-center text-gray-600 text-xs">
                        No violations in the selected window
                      </td>
                    </tr>
                  ) : violations.slice(0, 50).map(v => (
                    <ViolationRow key={v.id} v={v} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
