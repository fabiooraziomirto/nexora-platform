import { useState } from 'react'
import { RefreshCw, Search } from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'
import { SkeletonRows } from '../components/Skeleton'

export default function Audit() {
  const [action, setAction] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [actor, setActor] = useState('')
  const { data, loading, error, reload } = useApi(
    () => api.listAuditEvents({
      action: action || undefined,
      resource_type: resourceType || undefined,
      actor_user_id: actor || undefined,
      page_size: 200,
    }),
    [action, resourceType, actor],
  )

  const events = data?.items ?? []

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Audit</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} events` : loading ? '...' : '-'}
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

      <div className="mb-4 grid grid-cols-1 md:grid-cols-3 gap-2">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="w-full border border-slate-300 rounded bg-white pl-8 pr-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Action"
            value={action}
            onChange={e => setAction(e.target.value)}
          />
        </div>
        <input
          className="w-full border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Resource type"
          value={resourceType}
          onChange={e => setResourceType(e.target.value)}
        />
        <input
          className="w-full border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Actor user ID"
          value={actor}
          onChange={e => setActor(e.target.value)}
        />
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-2.5 mb-4">
          {error}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Time</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Action</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Resource</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Actor</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Tenant</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={6} cols={6} />
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-sm text-slate-400">No audit events found</td>
              </tr>
            ) : events.map((event, index) => (
              <tr key={`${event.timestamp}-${index}`} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 text-xs text-slate-500 whitespace-nowrap">
                  {new Date(event.timestamp).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{event.action}</td>
                <td className="px-4 py-2.5 text-xs text-slate-500">
                  <span className="font-medium text-slate-700">{event.resource_type}</span>
                  <span className="ml-1 font-mono">{event.resource_id?.slice(0, 8) ?? '-'}</span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{event.actor_user_id}</td>
                <td className="px-4 py-2.5 text-xs text-slate-500">{event.tenant_id ?? '-'}</td>
                <td className="px-4 py-2.5 text-xs text-slate-600">{event.outcome}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
