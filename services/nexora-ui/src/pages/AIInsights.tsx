import { useMemo, useState } from 'react'
import { BrainCircuit, Check, RefreshCw, Search, ShieldCheck, Wand2 } from 'lucide-react'
import { api, type AIInsight, type AIInsightCategory, type AIInsightSeverity, type AIInsightStatus } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import { SkeletonRows } from '../components/Skeleton'

const SELECT = 'border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

const SEVERITY_STYLE: Record<string, string> = {
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  warning: 'bg-orange-50 text-orange-700 border-orange-200',
  critical: 'bg-red-50 text-red-700 border-red-200',
}

const STATUS_STYLE: Record<string, string> = {
  open: 'bg-slate-900 text-white border-slate-900',
  acknowledged: 'bg-amber-50 text-amber-700 border-amber-200',
  resolved: 'bg-green-50 text-green-700 border-green-200',
}

function Pill({ value, kind }: { value: string; kind: 'severity' | 'status' }) {
  const style = kind === 'severity' ? SEVERITY_STYLE[value] : STATUS_STYLE[value]
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${style ?? 'bg-slate-50 text-slate-600 border-slate-200'}`}>
      {value}
    </span>
  )
}

function ModelBadge({ model }: { model: string }) {
  const isRules = model === 'rules'
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${
      isRules ? 'bg-slate-50 text-slate-600 border-slate-200' : 'bg-violet-50 text-violet-700 border-violet-200'
    }`}>
      <BrainCircuit size={12} />
      {isRules ? 'rules fallback' : model}
    </span>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export default function AIInsights() {
  const [severity, setSeverity] = useState<AIInsightSeverity | ''>('')
  const [status, setStatus] = useState<AIInsightStatus | ''>('open')
  const [category, setCategory] = useState<AIInsightCategory | ''>('')
  const [scopeId, setScopeId] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const toast = useToast()

  const filters = useMemo(() => ({
    severity,
    status,
    category,
    scope_id: scopeId.trim(),
  }), [severity, status, category, scopeId])

  const { data, loading, error, reload } = useApi(() => api.listAIInsights(filters), [filters])
  const insights = data?.items ?? []
  const selected = insights.find(i => i.id === selectedId) ?? insights[0] ?? null

  async function updateInsight(action: 'ack' | 'resolve', insight: AIInsight) {
    setActing(true)
    try {
      if (action === 'ack') {
        await api.acknowledgeAIInsight(insight.id)
        toast.show('success', 'Insight acknowledged')
      } else {
        await api.resolveAIInsight(insight.id)
        toast.show('success', 'Insight resolved')
      }
      await reload()
    } catch {
      toast.show('error', `Failed to ${action} insight`)
    } finally {
      setActing(false)
    }
  }

  async function enrichInsight(insight: AIInsight) {
    setActing(true)
    try {
      await api.enrichAIInsight(insight.id)
      await reload()
      toast.show('success', 'Insight enriched')
    } catch {
      toast.show('error', 'Failed to enrich insight')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">AI Insights</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} insight${data.total === 1 ? '' : 's'}` : loading ? 'Loading…' : 'AIOps recommendations'}
          </p>
        </div>
        <button
          onClick={reload}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-5">
        <select className={SELECT} value={severity} onChange={e => setSeverity(e.target.value as AIInsightSeverity | '')}>
          <option value="">All severities</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="critical">critical</option>
        </select>
        <select className={SELECT} value={status} onChange={e => setStatus(e.target.value as AIInsightStatus | '')}>
          <option value="">All statuses</option>
          <option value="open">open</option>
          <option value="acknowledged">acknowledged</option>
          <option value="resolved">resolved</option>
        </select>
        <select className={SELECT} value={category} onChange={e => setCategory(e.target.value as AIInsightCategory | '')}>
          <option value="">All categories</option>
          <option value="anomaly">anomaly</option>
          <option value="slo_breach">slo breach</option>
          <option value="execution_failure">execution failure</option>
          <option value="delivery_risk">delivery risk</option>
          <option value="operational_summary">operational summary</option>
        </select>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            className="border border-slate-300 rounded bg-white pl-8 pr-3 py-1.5 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-72"
            placeholder="Filter by scope ID…"
            value={scopeId}
            onChange={e => setScopeId(e.target.value)}
          />
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-2.5 mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)] gap-5">
        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Insight</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Severity</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && !data ? (
                <SkeletonRows rows={6} cols={4} />
              ) : insights.length === 0 ? (
                <tr>
                  <td colSpan={4}>
                    <div className="flex flex-col items-center py-16 text-slate-400">
                      <ShieldCheck size={34} className="mb-3 opacity-30" />
                      <p className="text-sm font-medium">No insights match the current filters</p>
                    </div>
                  </td>
                </tr>
              ) : insights.map(insight => (
                <tr
                  key={insight.id}
                  onClick={() => setSelectedId(insight.id)}
                  className={`cursor-pointer transition-colors ${selected?.id === insight.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{insight.title}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                      <span>{insight.category}</span>
                      <span className="text-slate-300">/</span>
                      <span className="font-mono">{insight.scope_id}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><Pill value={insight.severity} kind="severity" /></td>
                  <td className="px-4 py-3"><Pill value={insight.status} kind="status" /></td>
                  <td className="px-4 py-3 text-xs text-slate-400">{new Date(insight.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="bg-white border border-slate-200 rounded min-h-[420px]">
          {!selected ? (
            <div className="h-full min-h-[420px] flex flex-col items-center justify-center text-slate-400">
              <BrainCircuit size={34} className="mb-3 opacity-30" />
              <p className="text-sm font-medium">Select an insight</p>
            </div>
          ) : (
            <div className="p-5">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">{selected.title}</h2>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Pill value={selected.severity} kind="severity" />
                    <Pill value={selected.status} kind="status" />
                    <ModelBadge model={selected.model_used} />
                  </div>
                </div>
              </div>

              <p className="text-sm text-slate-700 leading-6 mb-5">{selected.summary}</p>

              {(selected.probable_cause || selected.confidence || selected.risk_score) && (
                <div className="grid grid-cols-1 gap-3 mb-5">
                  {selected.probable_cause && (
                    <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Probable Cause</div>
                      <div className="text-sm text-slate-700">{selected.probable_cause}</div>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {selected.confidence && <span className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">confidence {selected.confidence}</span>}
                    {selected.risk_score && <span className="rounded border border-orange-200 bg-orange-50 px-2 py-1 text-xs font-medium text-orange-700">risk {selected.risk_score}</span>}
                  </div>
                </div>
              )}

              <div className="mb-5">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Recommendations</h3>
                <ul className="space-y-2">
                  {selected.recommendations.map((item, index) => (
                    <li key={`${selected.id}-rec-${index}`} className="flex gap-2 text-sm text-slate-700">
                      <Check size={14} className="mt-0.5 text-green-600 shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {selected.runbook_steps && selected.runbook_steps.length > 0 && (
                <div className="mb-5">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Runbook</h3>
                  <ol className="space-y-2">
                    {selected.runbook_steps.map((step, index) => (
                      <li key={`${selected.id}-runbook-${index}`} className="flex gap-2 text-sm text-slate-700">
                        <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600">{index + 1}</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {selected.related_events && selected.related_events.length > 0 && (
                <div className="mb-5">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Related Events</h3>
                  <div className="space-y-2">
                    {selected.related_events.map((event, index) => (
                      <div key={`${selected.id}-related-${index}`} className="rounded border border-slate-200 px-3 py-2 text-xs text-slate-600">
                        <span className="font-medium text-slate-800">{formatValue(event.title)}</span>
                        <span className="ml-2 text-slate-400">{formatValue(event.category)} / {formatValue(event.severity)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mb-5">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Evidence</h3>
                <div className="border border-slate-200 rounded overflow-hidden">
                  {Object.entries(selected.evidence).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[140px_minmax(0,1fr)] border-b border-slate-100 last:border-b-0 text-sm">
                      <div className="bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500">{key}</div>
                      <div className="px-3 py-2 text-slate-700 font-mono text-xs break-words">{formatValue(value)}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  disabled={acting}
                  onClick={() => enrichInsight(selected)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-blue-200 bg-blue-50 text-sm text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Wand2 size={13} />
                  Enrich
                </button>
                <button
                  disabled={acting || selected.status !== 'open'}
                  onClick={() => updateInsight('ack', selected)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Acknowledge
                </button>
                <button
                  disabled={acting || selected.status === 'resolved'}
                  onClick={() => updateInsight('resolve', selected)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Resolve
                </button>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
