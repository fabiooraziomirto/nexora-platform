import { useState } from 'react'
import { RefreshCw, Plus, Trash2, Network, Link, Unlink } from 'lucide-react'
import { api, type PortCreate } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

interface FormState extends PortCreate { submitting: boolean; error: string }

const EMPTY_FORM: FormState = {
  device_id: '', network_id: '', ip_address: '', status: 'created',
  submitting: false, error: '',
}

export default function Ports() {
  const { data, loading, error, reload } = useApi(() => api.listPorts(1, 200))
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm]       = useState<FormState>(EMPTY_FORM)
  const [acting, setActing]   = useState<string | null>(null)
  const toast = useToast()

  const ports = data?.items ?? []

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      const p = await api.createPort({
        device_id: form.device_id.trim(),
        network_id: form.network_id.trim(),
        ip_address: form.ip_address.trim(),
        status: 'created',
      })
      setShowAdd(false)
      setForm(EMPTY_FORM)
      reload()
      toast.show('success', 'Port created', `ID: ${p.id}`)
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleAttach(id: string) {
    setActing(id)
    try {
      await api.updatePort(id, { status: 'attached' })
      reload()
      toast.show('success', 'Port attached')
    } catch {
      toast.show('error', 'Failed to attach port')
    } finally {
      setActing(null)
    }
  }

  async function handleDetach(id: string) {
    setActing(id)
    try {
      await api.updatePort(id, { status: 'detached' })
      reload()
      toast.show('info', 'Port detached')
    } catch {
      toast.show('error', 'Failed to detach port')
    } finally {
      setActing(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this port?')) return
    setActing(id)
    try {
      await api.deletePort(id)
      reload()
      toast.show('success', 'Port deleted')
    } catch {
      toast.show('error', 'Failed to delete port')
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Network Ports</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} ports` : loading ? '…' : '—'}
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
            Add Port
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
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Network</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">IP Address</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 w-24" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={5} cols={5} />
            ) : ports.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <div className="flex flex-col items-center py-14 text-slate-400">
                    <Network size={32} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">No ports yet</p>
                    <button
                      onClick={() => setShowAdd(true)}
                      className="mt-3 text-sm text-blue-600 hover:underline"
                    >
                      Add a port
                    </button>
                  </div>
                </td>
              </tr>
            ) : ports.map(p => (
              <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500" title={p.device_id}>
                  {p.device_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2.5 text-slate-700">{p.network_id}</td>
                <td className="px-4 py-2.5 font-mono text-sm text-slate-700">{p.ip_address}</td>
                <td className="px-4 py-2.5"><StatusBadge status={p.status} /></td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1 justify-end">
                    {(p.status === 'created' || p.status === 'detached') && (
                      <button
                        onClick={() => handleAttach(p.id)}
                        disabled={acting === p.id}
                        title="Attach"
                        className="p-1 rounded text-slate-300 hover:text-green-600 hover:bg-green-50 transition-colors disabled:opacity-40"
                      >
                        <Link size={14} />
                      </button>
                    )}
                    {p.status === 'attached' && (
                      <button
                        onClick={() => handleDetach(p.id)}
                        disabled={acting === p.id}
                        title="Detach"
                        className="p-1 rounded text-slate-300 hover:text-orange-500 hover:bg-orange-50 transition-colors disabled:opacity-40"
                      >
                        <Unlink size={14} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(p.id)}
                      disabled={acting === p.id}
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
        <Modal title="Add Network Port" onClose={() => { setShowAdd(false); setForm(EMPTY_FORM) }}>
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
                Network ID <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. default-network"
                value={form.network_id} onChange={e => setForm(f => ({ ...f, network_id: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                IP Address <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="10.0.0.1"
                value={form.ip_address} onChange={e => setForm(f => ({ ...f, ip_address: e.target.value }))} />
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
                {form.submitting ? 'Adding…' : 'Add Port'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
