import { useState } from 'react'
import { AlertCircle, Plus, Trash2, RefreshCw } from 'lucide-react'
import { api, type SLO as SLOType } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

const OPERATORS = ['lt', 'lte', 'gt', 'gte', 'eq']
const OP_LABEL: Record<string, string> = { lt: '<', lte: '≤', gt: '>', gte: '≥', eq: '=' }
const SELECT = 'border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

export default function SLO() {
  const { data: devices } = useApi(() => api.listDevices(1, 200))
  const [deviceId, setDeviceId] = useState('')
  const [hours, setHours]       = useState(24)
  const toast = useToast()

  const { data: slos, loading: loadingSLOs, reload: reloadSLOs } = useApi(
    () => deviceId ? api.listSLOs(deviceId) : Promise.resolve([] as SLOType[]),
    [deviceId]
  )
  const { data: violations, loading: loadingViolations, reload: reloadViolations } = useApi(
    () => deviceId ? api.listViolations(deviceId, hours) : Promise.resolve([]),
    [deviceId, hours]
  )

  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm]       = useState({ metric: '', operator: 'lt', threshold: '', submitting: false, error: '' })
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!deviceId || !form.metric || !form.threshold) return
    setForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      await api.createSLO(deviceId, {
        metric: form.metric.trim(),
        operator: form.operator,
        threshold: parseFloat(form.threshold),
      })
      setShowAdd(false)
      setForm({ metric: '', operator: 'lt', threshold: '', submitting: false, error: '' })
      reloadSLOs()
      toast.show('success', 'SLO created')
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleDelete(sloId: string, metric: string) {
    if (!confirm(`Delete SLO for "${metric}"?`)) return
    setDeleting(sloId)
    try {
      await api.deleteSLO(deviceId, sloId)
      reloadSLOs()
      toast.show('success', `SLO for "${metric}" deleted`)
    } catch {
      toast.show('error', 'Failed to delete SLO')
    } finally {
      setDeleting(null)
    }
  }

  const deviceName = devices?.items.find(d => d.id === deviceId)?.name

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">SLOs & Violations</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {deviceName ?? 'Select a device'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { reloadSLOs(); reloadViolations() }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw size={13} className={(loadingSLOs || loadingViolations) ? 'animate-spin' : ''} />
            Refresh
          </button>
          {deviceId && (
            <button
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              <Plus size={14} />
              New SLO
            </button>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 mb-5">
        <select className={SELECT} value={deviceId} onChange={e => setDeviceId(e.target.value)}>
          <option value="">Select device…</option>
          {devices?.items.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        {deviceId && (
          <select className={SELECT} value={hours} onChange={e => setHours(Number(e.target.value))}>
            {[1, 6, 24, 48, 168].map(h => (
              <option key={h} value={h}>Violations: last {h}h</option>
            ))}
          </select>
        )}
      </div>

      {!deviceId ? (
        <div className="bg-white border border-slate-200 rounded py-20 flex flex-col items-center text-slate-400">
          <AlertCircle size={36} className="mb-3 opacity-25" />
          <p className="text-sm font-medium">Select a device to manage SLOs</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

          {/* SLO definitions */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Defined SLOs</h2>
              <span className="text-xs text-slate-400">{slos?.length ?? 0} rule{slos?.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="bg-white border border-slate-200 rounded overflow-hidden">
              {loadingSLOs ? (
                <table className="w-full"><tbody><SkeletonRows rows={3} cols={3} /></tbody></table>
              ) : !slos || slos.length === 0 ? (
                <div className="py-12 flex flex-col items-center text-slate-400">
                  <p className="text-sm">No SLOs defined</p>
                  <button
                    onClick={() => setShowAdd(true)}
                    className="mt-2 text-sm text-blue-600 hover:underline"
                  >
                    Create the first SLO
                  </button>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Metric</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Condition</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">State</th>
                      <th className="px-4 py-2.5 w-10" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {slos.map(s => (
                      <tr key={s.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 font-medium text-slate-900">{s.metric}</td>
                        <td className="px-4 py-2.5 text-slate-600 font-mono text-xs">
                          {OP_LABEL[s.operator]} {s.threshold}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium border ${
                            s.enabled
                              ? 'bg-green-50 text-green-700 border-green-200'
                              : 'bg-slate-50 text-slate-500 border-slate-200'
                          }`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${s.enabled ? 'bg-green-500' : 'bg-slate-400'}`} />
                            {s.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <button
                            onClick={() => handleDelete(s.id, s.metric)}
                            disabled={deleting === s.id}
                            className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Violations */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Recent Violations</h2>
              {violations && violations.length > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-red-100 text-red-700 text-xs font-medium px-1.5 py-0.5 min-w-[1.25rem]">
                  {violations.length}
                </span>
              )}
            </div>
            <div className="bg-white border border-slate-200 rounded overflow-hidden">
              {loadingViolations ? (
                <table className="w-full"><tbody><SkeletonRows rows={4} cols={3} /></tbody></table>
              ) : !violations || violations.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-sm">
                  No violations in the selected window
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Metric</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Observed</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {violations.slice(0, 50).map(v => (
                      <tr key={v.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 text-slate-700 font-medium">{v.metric}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-red-600">
                          {v.observed_value.toFixed(3)} {OP_LABEL[v.operator]} {v.threshold}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs">
                          {new Date(v.violated_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* New SLO modal */}
      {showAdd && (
        <Modal title="New SLO Rule" onClose={() => { setShowAdd(false); setForm({ metric: '', operator: 'lt', threshold: '', submitting: false, error: '' }) }}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Metric <span className="text-red-500">*</span>
              </label>
              <input
                required autoFocus
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. temperature"
                value={form.metric}
                onChange={e => setForm(f => ({ ...f, metric: e.target.value }))}
              />
            </div>
            <div className="flex gap-3">
              <div className="w-40">
                <label className="block text-xs font-medium text-slate-700 mb-1">Condition</label>
                <select
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  value={form.operator}
                  onChange={e => setForm(f => ({ ...f, operator: e.target.value }))}
                >
                  {OPERATORS.map(op => (
                    <option key={op} value={op}>{OP_LABEL[op]}  ({op})</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Threshold <span className="text-red-500">*</span>
                </label>
                <input
                  required
                  type="number"
                  step="any"
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g. 80"
                  value={form.threshold}
                  onChange={e => setForm(f => ({ ...f, threshold: e.target.value }))}
                />
              </div>
            </div>
            {form.threshold && form.metric && (
              <p className="text-xs text-slate-500 bg-slate-50 rounded px-3 py-2 border border-slate-200">
                Alert when <span className="font-medium text-slate-700">{form.metric}</span> {OP_LABEL[form.operator]} <span className="font-medium text-slate-700">{form.threshold}</span>
              </p>
            )}
            {form.error && <p className="text-xs text-red-600">{form.error}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => { setShowAdd(false); setForm({ metric: '', operator: 'lt', threshold: '', submitting: false, error: '' }) }}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={form.submitting}
                className="px-4 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {form.submitting ? 'Creating…' : 'Create SLO'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
