import { useState } from 'react'
import { RefreshCw, Plus, Trash2, Globe, ToggleLeft, ToggleRight, Lock, Unlock } from 'lucide-react'
import { api, type WebserviceCreate } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

interface FormState {
  device_id: string
  hostname: string
  port: string
  tls_enabled: boolean
  submitting: boolean
  error: string
}

const EMPTY_FORM: FormState = {
  device_id: '', hostname: '', port: '80', tls_enabled: false, submitting: false, error: '',
}

export default function Webservices() {
  const { data, loading, error, reload } = useApi(() => api.listWebservices(1, 200))
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm]       = useState<FormState>(EMPTY_FORM)
  const [acting, setActing]   = useState<string | null>(null)
  const toast = useToast()

  const webservices = data?.items ?? []

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    const portNum = parseInt(form.port, 10)
    if (!portNum || portNum < 1 || portNum > 65535) {
      setForm(f => ({ ...f, error: 'Port must be 1–65535' }))
      return
    }
    setForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      const body: WebserviceCreate = {
        device_id: form.device_id.trim(),
        hostname: form.hostname.trim(),
        port: portNum,
        tls_enabled: form.tls_enabled,
        status: 'enabled',
      }
      const ws = await api.createWebservice(body)
      setShowAdd(false)
      setForm(EMPTY_FORM)
      reload()
      toast.show('success', 'Webservice registered', `ID: ${ws.id}`)
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleToggle(id: string, currentStatus: string) {
    const newStatus = currentStatus === 'enabled' ? 'disabled' : 'enabled'
    setActing(id)
    try {
      await api.updateWebservice(id, { status: newStatus })
      reload()
      toast.show('info', `Webservice ${newStatus}`)
    } catch {
      toast.show('error', `Failed to ${newStatus} webservice`)
    } finally {
      setActing(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this webservice?')) return
    setActing(id)
    try {
      await api.deleteWebservice(id)
      reload()
      toast.show('success', 'Webservice deleted')
    } catch {
      toast.show('error', 'Failed to delete webservice')
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Webservices</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} endpoints` : loading ? '…' : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={reload}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus size={14} />
            Register Webservice
          </button>
        </div>
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
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Device</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Endpoint</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">TLS</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 w-24" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={5} cols={5} />
            ) : webservices.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <div className="flex flex-col items-center py-14 text-slate-400">
                    <Globe size={32} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">No webservices yet</p>
                    <button
                      onClick={() => setShowAdd(true)}
                      className="mt-3 text-sm text-blue-600 hover:underline"
                    >
                      Register an endpoint
                    </button>
                  </div>
                </td>
              </tr>
            ) : webservices.map(ws => (
              <tr key={ws.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500" title={ws.device_id}>
                  {ws.device_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2.5 font-medium text-slate-900">
                  <span className="font-mono text-xs text-slate-500 mr-1">{ws.tls_enabled ? 'https' : 'http'}://</span>
                  {ws.hostname}:{ws.port}
                </td>
                <td className="px-4 py-2.5">
                  {ws.tls_enabled
                    ? <span className="inline-flex items-center gap-1 text-xs text-green-700"><Lock size={12} />TLS</span>
                    : <span className="inline-flex items-center gap-1 text-xs text-slate-400"><Unlock size={12} />None</span>
                  }
                </td>
                <td className="px-4 py-2.5"><StatusBadge status={ws.status} /></td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1 justify-end">
                    <button
                      onClick={() => handleToggle(ws.id, ws.status)}
                      disabled={acting === ws.id}
                      title={ws.status === 'enabled' ? 'Disable' : 'Enable'}
                      className="p-1 rounded text-slate-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40"
                    >
                      {ws.status === 'enabled'
                        ? <ToggleRight size={16} className="text-green-500" />
                        : <ToggleLeft size={16} />
                      }
                    </button>
                    <button
                      onClick={() => handleDelete(ws.id)}
                      disabled={acting === ws.id}
                      title="Delete"
                      className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <Modal title="Register Webservice" onClose={() => { setShowAdd(false); setForm(EMPTY_FORM) }}>
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Device ID <span className="text-red-500">*</span>
              </label>
              <input required autoFocus
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="uuid"
                value={form.device_id} onChange={e => setForm(f => ({ ...f, device_id: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Hostname <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="board.local"
                value={form.hostname} onChange={e => setForm(f => ({ ...f, hostname: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Port <span className="text-red-500">*</span>
              </label>
              <input required type="number" min={1} max={65535}
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.port} onChange={e => setForm(f => ({ ...f, port: e.target.value }))} />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="tls"
                checked={form.tls_enabled}
                onChange={e => setForm(f => ({ ...f, tls_enabled: e.target.checked }))}
                className="rounded border-slate-300"
              />
              <label htmlFor="tls" className="text-sm text-slate-700 select-none cursor-pointer">
                TLS enabled (HTTPS)
              </label>
            </div>
            {form.error && <p className="text-xs text-red-600">{form.error}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <button type="button"
                onClick={() => { setShowAdd(false); setForm(EMPTY_FORM) }}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={form.submitting}
                className="px-4 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {form.submitting ? 'Registering…' : 'Register'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
