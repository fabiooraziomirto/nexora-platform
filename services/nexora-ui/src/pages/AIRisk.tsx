import { useState } from 'react'
import { Gauge, RefreshCw } from 'lucide-react'
import { api, type AIRiskScore } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'

const SELECT = 'border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

const LEVEL: Record<string, string> = {
  low: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  high: 'bg-orange-50 text-orange-700 border-orange-200',
  critical: 'bg-red-50 text-red-700 border-red-200',
}

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  return (
    <div className="border border-slate-200 rounded overflow-hidden">
      {Object.entries(evidence).map(([key, value]) => (
        <div key={key} className="grid grid-cols-[160px_minmax(0,1fr)] border-b border-slate-100 last:border-b-0 text-sm">
          <div className="bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500">{key}</div>
          <div className="px-3 py-2 text-slate-700 font-mono text-xs break-words">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</div>
        </div>
      ))}
    </div>
  )
}

export default function AIRisk() {
  const [scopeType, setScopeType] = useState<'device' | 'fleet'>('device')
  const [scopeId, setScopeId] = useState('')
  const [risk, setRisk] = useState<AIRiskScore | null>(null)
  const [loading, setLoading] = useState(false)
  const toast = useToast()
  const { data: devices } = useApi(() => api.listDevices(1, 200))
  const { data: fleets } = useApi(() => api.listFleets())

  async function loadRisk() {
    if (!scopeId) return
    setLoading(true)
    try {
      const next = scopeType === 'device' ? await api.getDeviceRisk(scopeId) : await api.getFleetRisk(scopeId)
      setRisk(next)
    } catch {
      toast.show('error', 'Failed to compute risk')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">AI Risk</h1>
          <p className="text-sm text-slate-500 mt-0.5">Device and fleet operational risk scoring</p>
        </div>
        <button onClick={loadRisk} disabled={!scopeId || loading} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Recompute
        </button>
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        <select className={SELECT} value={scopeType} onChange={e => { setScopeType(e.target.value as 'device' | 'fleet'); setScopeId(''); setRisk(null) }}>
          <option value="device">Device</option>
          <option value="fleet">Fleet</option>
        </select>
        <select className={SELECT} value={scopeId} onChange={e => { setScopeId(e.target.value); setRisk(null) }}>
          <option value="">Select {scopeType}…</option>
          {scopeType === 'device'
            ? devices?.items.map(d => <option key={d.id} value={d.id}>{d.name}</option>)
            : fleets?.items.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
      </div>

      {!risk ? (
        <div className="bg-white border border-slate-200 rounded py-20 flex flex-col items-center text-slate-400">
          <Gauge size={36} className="mb-3 opacity-30" />
          <p className="text-sm font-medium">Select a scope and compute risk</p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded p-5 max-w-4xl">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-slate-900">{risk.scope_type} / {risk.scope_id}</h2>
              <p className="text-xs text-slate-400 mt-1">Updated {new Date(risk.updated_at).toLocaleString()}</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-semibold text-slate-900">{risk.score}</div>
              <span className={`rounded border px-2 py-1 text-xs font-medium ${LEVEL[risk.level]}`}>{risk.level}</span>
            </div>
          </div>
          <Evidence evidence={risk.evidence} />
        </div>
      )}
    </div>
  )
}
