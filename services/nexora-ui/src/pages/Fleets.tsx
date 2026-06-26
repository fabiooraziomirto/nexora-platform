import { useState } from 'react'
import { RefreshCw, Plus, Trash2, UserPlus, Layers } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

export default function Fleets() {
  const { data: fleets, loading: loadingFleets, reload: reloadFleets } = useApi(() => api.listFleets())
  const { data: allDevices } = useApi(() => api.listDevices(1, 200))
  const [selectedId, setSelectedId] = useState('')
  const toast = useToast()

  const { data: health, loading: loadingHealth, reload: reloadHealth } = useApi(
    () => selectedId ? api.getFleetHealth(selectedId) : Promise.resolve(null),
    [selectedId]
  )

  const [showCreateFleet, setShowCreateFleet] = useState(false)
  const [fleetForm, setFleetForm]             = useState({ name: '', description: '', submitting: false, error: '' })
  const [showAddMember, setShowAddMember]     = useState(false)
  const [memberDeviceId, setMemberDeviceId]   = useState('')
  const [memberSubmitting, setMemberSubmitting] = useState(false)
  const [deletingFleet, setDeletingFleet]     = useState(false)
  const [removingMember, setRemovingMember]   = useState<string | null>(null)

  const summaryData = health
    ? [
        { name: 'Online',  value: health.summary.online,  fill: '#22c55e' },
        { name: 'Offline', value: health.summary.offline, fill: '#ef4444' },
        { name: 'Unknown', value: health.summary.unknown, fill: '#94a3b8' },
      ]
    : []

  // Devices not already in this fleet
  const memberIds = new Set(health?.devices.map(d => d.device_id) ?? [])
  const availableDevices = allDevices?.items.filter(d => !memberIds.has(d.id)) ?? []

  async function handleCreateFleet(e: React.FormEvent) {
    e.preventDefault()
    setFleetForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      const fleet = await api.createFleet({ name: fleetForm.name.trim(), description: fleetForm.description || undefined })
      setShowCreateFleet(false)
      setFleetForm({ name: '', description: '', submitting: false, error: '' })
      await reloadFleets()
      setSelectedId(fleet.id)
      toast.show('success', `Fleet "${fleet.name}" created`)
    } catch (err) {
      setFleetForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleDeleteFleet() {
    if (!selectedId) return
    const name = fleets?.items.find(f => f.id === selectedId)?.name ?? selectedId
    if (!confirm(`Delete fleet "${name}"? This action cannot be undone.`)) return
    setDeletingFleet(true)
    try {
      await api.deleteFleet(selectedId)
      setSelectedId('')
      reloadFleets()
      toast.show('success', `Fleet "${name}" deleted`)
    } catch {
      toast.show('error', 'Failed to delete fleet')
    } finally {
      setDeletingFleet(false)
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedId || !memberDeviceId) return
    setMemberSubmitting(true)
    try {
      const device = allDevices?.items.find(d => d.id === memberDeviceId)
      await api.addFleetMember(selectedId, memberDeviceId)
      setShowAddMember(false)
      setMemberDeviceId('')
      reloadHealth()
      toast.show('success', `"${device?.name ?? memberDeviceId}" added to fleet`)
    } catch (err) {
      toast.show('error', `Failed to add member: ${err}`)
    } finally {
      setMemberSubmitting(false)
    }
  }

  async function handleRemoveMember(deviceId: string, name: string) {
    if (!selectedId) return
    if (!confirm(`Remove "${name}" from this fleet?`)) return
    setRemovingMember(deviceId)
    try {
      await api.removeFleetMember(selectedId, deviceId)
      reloadHealth()
      toast.show('success', `"${name}" removed from fleet`)
    } catch {
      toast.show('error', 'Failed to remove member')
    } finally {
      setRemovingMember(null)
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Fleets</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {fleets ? `${fleets.total} fleet${fleets.total !== 1 ? 's' : ''}` : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { reloadFleets(); if (selectedId) reloadHealth() }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw size={13} className={loadingHealth ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateFleet(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus size={14} />
            Create Fleet
          </button>
        </div>
      </div>

      <div className="flex gap-5">
        {/* Fleet sidebar */}
        <div className="w-48 shrink-0 bg-white border border-slate-200 rounded overflow-hidden self-start">
          <div className="px-3 py-2 border-b border-slate-100 text-xs font-medium text-slate-500 uppercase tracking-wide">
            Fleets
          </div>
          {loadingFleets ? (
            <div className="p-3 space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-8 bg-slate-100 rounded animate-pulse" />)}
            </div>
          ) : !fleets?.items.length ? (
            <div className="px-3 py-6 text-center">
              <p className="text-xs text-slate-400">No fleets yet</p>
              <button onClick={() => setShowCreateFleet(true)} className="mt-1.5 text-xs text-blue-600 hover:underline">
                Create one
              </button>
            </div>
          ) : fleets.items.map(f => (
            <button
              key={f.id}
              onClick={() => setSelectedId(f.id)}
              className={`w-full text-left px-3 py-2.5 text-sm border-b border-slate-100 last:border-0 transition-colors ${
                selectedId === f.id
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-slate-700 hover:bg-slate-50'
              }`}
            >
              <div className="truncate">{f.name}</div>
              {f.description && (
                <div className="text-xs text-slate-400 truncate mt-0.5">{f.description}</div>
              )}
            </button>
          ))}
        </div>

        {/* Fleet detail */}
        <div className="flex-1 min-w-0">
          {!selectedId ? (
            <div className="bg-white border border-slate-200 rounded py-20 flex flex-col items-center text-slate-400">
              <Layers size={36} className="mb-3 opacity-25" />
              <p className="text-sm font-medium">Select a fleet to view details</p>
            </div>
          ) : loadingHealth ? (
            <div className="bg-white border border-slate-200 rounded">
              <table className="w-full"><tbody><SkeletonRows rows={4} cols={4} /></tbody></table>
            </div>
          ) : health ? (
            <>
              {/* Fleet header */}
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-slate-900">{health.fleet_name}</h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowAddMember(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                    disabled={availableDevices.length === 0}
                    title={availableDevices.length === 0 ? 'All registered devices are already in this fleet' : undefined}
                  >
                    <UserPlus size={13} />
                    Add Device
                  </button>
                  <button
                    onClick={handleDeleteFleet}
                    disabled={deletingFleet}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-red-200 bg-white text-sm text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={13} />
                    Delete Fleet
                  </button>
                </div>
              </div>

              {/* Summary cards */}
              <div className="grid grid-cols-4 gap-3 mb-4">
                {[
                  { label: 'Total',   value: health.summary.total,   color: 'text-slate-900' },
                  { label: 'Online',  value: health.summary.online,  color: 'text-green-600' },
                  { label: 'Offline', value: health.summary.offline, color: 'text-red-600' },
                  { label: 'Unknown', value: health.summary.unknown, color: 'text-slate-400' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-white border border-slate-200 rounded p-4 text-center">
                    <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</p>
                    <p className={`text-3xl font-bold mt-1 tabular-nums ${color}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Bar chart */}
              {health.summary.total > 0 && (
                <div className="bg-white border border-slate-200 rounded p-4 mb-4">
                  <ResponsiveContainer width="100%" height={110}>
                    <BarChart data={summaryData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 4, fontSize: 12 }}
                      />
                      <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                        {summaryData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Members table */}
              <div className="bg-white border border-slate-200 rounded overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Device</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Last seen</th>
                      <th className="px-4 py-2.5 w-10" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {health.devices.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-10 text-center text-slate-400 text-sm">
                          No devices in this fleet yet
                        </td>
                      </tr>
                    ) : health.devices.map(d => (
                      <tr key={d.device_id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-2.5 font-medium text-slate-900">{d.name ?? d.device_id.slice(0, 8)}</td>
                        <td className="px-4 py-2.5 text-slate-500">{d.device_type ?? '—'}</td>
                        <td className="px-4 py-2.5"><StatusBadge status={d.status} /></td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs">
                          {d.last_seen ? new Date(d.last_seen).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-2.5">
                          <button
                            onClick={() => handleRemoveMember(d.device_id, d.name ?? d.device_id.slice(0, 8))}
                            disabled={removingMember === d.device_id}
                            className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                            title="Remove from fleet"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Create Fleet modal */}
      {showCreateFleet && (
        <Modal title="Create Fleet" onClose={() => { setShowCreateFleet(false); setFleetForm({ name: '', description: '', submitting: false, error: '' }) }}>
          <form onSubmit={handleCreateFleet} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                required autoFocus
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. factory-floor-a"
                value={fleetForm.name}
                onChange={e => setFleetForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Description</label>
              <input
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Optional"
                value={fleetForm.description}
                onChange={e => setFleetForm(f => ({ ...f, description: e.target.value }))}
              />
            </div>
            {fleetForm.error && <p className="text-xs text-red-600">{fleetForm.error}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => { setShowCreateFleet(false); setFleetForm({ name: '', description: '', submitting: false, error: '' }) }}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={fleetForm.submitting}
                className="px-4 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {fleetForm.submitting ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Member modal */}
      {showAddMember && (
        <Modal title="Add Device to Fleet" onClose={() => { setShowAddMember(false); setMemberDeviceId('') }}>
          <form onSubmit={handleAddMember} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Device <span className="text-red-500">*</span>
              </label>
              {availableDevices.length === 0 ? (
                <p className="text-sm text-slate-500 py-2">All registered devices are already in this fleet.</p>
              ) : (
                <select
                  required autoFocus
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  value={memberDeviceId}
                  onChange={e => setMemberDeviceId(e.target.value)}
                >
                  <option value="">Select a device…</option>
                  {availableDevices.map(d => (
                    <option key={d.id} value={d.id}>{d.name} ({d.device_type})</option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => { setShowAddMember(false); setMemberDeviceId('') }}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={memberSubmitting || availableDevices.length === 0}
                className="px-4 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {memberSubmitting ? 'Adding…' : 'Add to Fleet'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
