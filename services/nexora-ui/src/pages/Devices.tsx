import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Search, Plus, Trash2, Monitor } from 'lucide-react'
import { api, type DeviceCreate } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'
import { useAuth } from '../auth/AuthContext'

interface FormState extends DeviceCreate { submitting: boolean; error: string }
const EMPTY_FORM: FormState = { name: '', device_type: '', description: '', submitting: false, error: '' }

export default function Devices() {
  const { data, loading, error, reload } = useApi(() => api.listDevices(1, 200))
  const {
    data: pendingData,
    loading: pendingLoading,
    error: pendingError,
    reload: reloadPending,
  } = useApi(() => api.listPendingDevices())
  const [search, setSearch]     = useState('')
  const [showAdd, setShowAdd]   = useState(false)
  const [form, setForm]         = useState<FormState>(EMPTY_FORM)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [pairingAction, setPairingAction] = useState<string | null>(null)
  const navigate = useNavigate()
  const toast = useToast()
  const auth = useAuth()
  const writePermissionHint = 'Write permission required (operator, tenant-admin, or platform-admin)'

  const devices = data?.items.filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.device_type.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  const pendingDevices = pendingData?.filter(d =>
    d.hardware_id.toLowerCase().includes(search.toLowerCase()) ||
    d.device_type.toLowerCase().includes(search.toLowerCase()) ||
    d.user_code.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  const reloadAll = () => {
    reload()
    reloadPending()
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      const created = await api.createDevice({
        name: form.name.trim(),
        device_type: form.device_type.trim(),
        description: form.description || undefined,
      })
      setShowAdd(false)
      setForm(EMPTY_FORM)
      reloadAll()
      toast.show('success', `Device "${created.name}" registered`, `ID: ${created.id}`)
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleDelete(e: React.MouseEvent, id: string, name: string) {
    e.stopPropagation()
    if (!confirm(`Delete "${name}"? This action cannot be undone.`)) return
    setDeleting(id)
    try {
      await api.deleteDevice(id)
      reloadAll()
      toast.show('success', `Device "${name}" deleted`)
    } catch {
      toast.show('error', 'Failed to delete device')
    } finally {
      setDeleting(null)
    }
  }

  async function handleApprovePending(discoveryId: string, hardwareId: string) {
    const suggestedName = `device-${hardwareId.slice(-6)}`
    const name = prompt('Device name for approval:', suggestedName)?.trim()
    if (!name) return
    setPairingAction(discoveryId)
    try {
      const claimed = await api.claimPendingDevice(discoveryId, { name })
      reloadAll()
      toast.show('success', `Pending device approved`, `Created device: ${claimed.name}`)
    } catch (err) {
      toast.show('error', 'Failed to approve pending device', String(err))
    } finally {
      setPairingAction(null)
    }
  }

  async function handleRejectPending(discoveryId: string) {
    if (!confirm('Reject this pending device?')) return
    setPairingAction(discoveryId)
    try {
      await api.rejectPendingDevice(discoveryId)
      reloadAll()
      toast.show('success', 'Pending device rejected')
    } catch (err) {
      toast.show('error', 'Failed to reject pending device', String(err))
    } finally {
      setPairingAction(null)
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Devices</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} registered` : loading ? '…' : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={reloadAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowAdd(true)}
            disabled={!auth.canWrite}
            title={!auth.canWrite ? writePermissionHint : undefined}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus size={14} />
            Register Device
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-xs">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          className="w-full border border-slate-300 rounded bg-white pl-8 pr-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="Filter by name or type…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-2.5 mb-4">
          {error}
        </div>
      )}

      {pendingError && (
        <div className="rounded border border-amber-200 bg-amber-50 text-amber-800 text-sm px-4 py-2.5 mb-4">
          Pending discovery list unavailable: {pendingError}
        </div>
      )}

      {!auth.canWrite && (
        <div className="rounded border border-indigo-200 bg-indigo-50 text-indigo-800 text-sm px-4 py-2.5 mb-4">
          Read-only mode: actions are disabled for your current role. {writePermissionHint}.
        </div>
      )}

      <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm font-medium text-amber-900">In attesa di collegamento</p>
          <p className="text-sm text-amber-800">
            {pendingLoading ? '…' : `${pendingDevices.length} pending`}
          </p>
        </div>
        {pendingDevices.length > 0 && (
          <div className="mt-2 overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-amber-800">
                  <th className="px-2 py-1 text-left text-xs font-medium uppercase tracking-wide">Hardware ID</th>
                  <th className="px-2 py-1 text-left text-xs font-medium uppercase tracking-wide">Type</th>
                  <th className="px-2 py-1 text-left text-xs font-medium uppercase tracking-wide">User Code</th>
                  <th className="px-2 py-1 text-left text-xs font-medium uppercase tracking-wide">Announced</th>
                  <th className="px-2 py-1 text-right text-xs font-medium uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingDevices.map(d => (
                  <tr key={d.discovery_id} className="border-t border-amber-100 text-amber-900">
                    <td className="px-2 py-1.5 font-mono text-xs">{d.hardware_id}</td>
                    <td className="px-2 py-1.5">{d.device_type}</td>
                    <td className="px-2 py-1.5 font-semibold">{d.user_code}</td>
                    <td className="px-2 py-1.5 text-xs">
                      {new Date(d.announced_at).toLocaleString()}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleApprovePending(d.discovery_id, d.hardware_id)}
                          disabled={!auth.canWrite || pairingAction === d.discovery_id}
                          title={!auth.canWrite ? writePermissionHint : undefined}
                          className="px-2 py-1 rounded bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleRejectPending(d.discovery_id)}
                          disabled={!auth.canWrite || pairingAction === d.discovery_id}
                          title={!auth.canWrite ? writePermissionHint : undefined}
                          className="px-2 py-1 rounded border border-amber-300 text-amber-900 text-xs font-medium hover:bg-amber-100 disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Name</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Last seen</th>
              <th className="px-4 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={5} cols={5} />
            ) : devices.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <div className="flex flex-col items-center py-14 text-slate-400">
                    <Monitor size={32} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">No devices found</p>
                    {!search && (
                      <button
                        onClick={() => setShowAdd(true)}
                        disabled={!auth.canWrite}
                        title={!auth.canWrite ? writePermissionHint : undefined}
                        className="mt-3 text-sm text-blue-600 hover:underline"
                      >
                        Register your first device
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : devices.map(d => (
              <tr
                key={d.id}
                onClick={() => navigate(`/telemetry?device=${d.id}`)}
                className="hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-2.5 font-medium text-slate-900">{d.name}</td>
                <td className="px-4 py-2.5 text-slate-500">{d.device_type}</td>
                <td className="px-4 py-2.5"><StatusBadge status={d.status} /></td>
                <td className="px-4 py-2.5 text-slate-400 text-xs">
                  {d.last_seen ? new Date(d.last_seen).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-2.5">
                  <button
                    onClick={e => handleDelete(e, d.id, d.name)}
                    disabled={deleting === d.id || !auth.canWrite}
                    className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                    title={!auth.canWrite ? writePermissionHint : 'Delete device'}
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Register Device modal */}
      {showAdd && (
        <Modal title="Register New Device" onClose={() => { setShowAdd(false); setForm(EMPTY_FORM) }}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                required autoFocus
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. sensor-floor-3"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Device Type <span className="text-red-500">*</span>
              </label>
              <input
                required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. temperature-sensor"
                value={form.device_type}
                onChange={e => setForm(f => ({ ...f, device_type: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Description</label>
              <textarea
                rows={2}
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                placeholder="Optional"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              />
            </div>
            {form.error && <p className="text-xs text-red-600">{form.error}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => { setShowAdd(false); setForm(EMPTY_FORM) }}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={form.submitting}
                className="px-4 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {form.submitting ? 'Registering…' : 'Register'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
