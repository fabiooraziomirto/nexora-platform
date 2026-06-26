import { useState } from 'react'
import { RefreshCw, Plus, Trash2, Package, CheckCircle, XCircle } from 'lucide-react'
import { api, type PluginCreate } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

interface FormState extends PluginCreate { submitting: boolean; error: string }

const EMPTY_FORM: FormState = {
  name: '', version: '1.0.0', module_type: 'function',
  artifact_uri: '', artifact_checksum: '', runtime_type: 'wasm-wasi',
  entrypoint: '_start', timeout_seconds: 30, memory_limit_mb: 64,
  permissions: [], submitting: false, error: '',
}

export default function Plugins() {
  const { data, loading, error, reload } = useApi(() => api.listPlugins(1, 200))
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm]       = useState<FormState>(EMPTY_FORM)
  const [acting, setActing]   = useState<string | null>(null)
  const toast = useToast()

  const plugins = data?.items ?? []

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setForm(f => ({ ...f, submitting: true, error: '' }))
    try {
      const p = await api.createPlugin({
        name: form.name.trim(),
        version: form.version.trim(),
        module_type: form.module_type,
        artifact_uri: form.artifact_uri.trim(),
        artifact_checksum: form.artifact_checksum.trim(),
        runtime_type: form.runtime_type,
        entrypoint: form.entrypoint || '_start',
        timeout_seconds: Number(form.timeout_seconds) || 30,
        memory_limit_mb: Number(form.memory_limit_mb) || 64,
        permissions: [],
      })
      setShowAdd(false)
      setForm(EMPTY_FORM)
      reload()
      toast.show('success', `Plugin "${p.name}" created`, `ID: ${p.id}`)
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleActivate(id: string, name: string) {
    setActing(id)
    try {
      await api.activatePlugin(id)
      reload()
      toast.show('success', `Plugin "${name}" activated`)
    } catch {
      toast.show('error', 'Failed to activate plugin')
    } finally {
      setActing(null)
    }
  }

  async function handleDeprecate(id: string, name: string) {
    if (!confirm(`Deprecate "${name}"?`)) return
    setActing(id)
    try {
      await api.deprecatePlugin(id)
      reload()
      toast.show('info', `Plugin "${name}" deprecated`)
    } catch {
      toast.show('error', 'Failed to deprecate plugin')
    } finally {
      setActing(null)
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete plugin "${name}"? This cannot be undone.`)) return
    setActing(id)
    try {
      await api.deletePlugin(id)
      reload()
      toast.show('success', `Plugin "${name}" deleted`)
    } catch {
      toast.show('error', 'Failed to delete plugin')
    } finally {
      setActing(null)
    }
  }

  function field(key: keyof FormState, value: string) {
    setForm(f => ({ ...f, [key]: value }))
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Plugins</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} registered` : loading ? '…' : '—'}
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
            New Plugin
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
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Name</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Version</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Runtime</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Created</th>
              <th className="px-4 py-2.5 w-28" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={5} cols={7} />
            ) : plugins.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <div className="flex flex-col items-center py-14 text-slate-400">
                    <Package size={32} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">No plugins yet</p>
                    <button
                      onClick={() => setShowAdd(true)}
                      className="mt-3 text-sm text-blue-600 hover:underline"
                    >
                      Create your first plugin
                    </button>
                  </div>
                </td>
              </tr>
            ) : plugins.map(p => (
              <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2.5 font-medium text-slate-900">{p.name}</td>
                <td className="px-4 py-2.5 text-slate-500 font-mono text-xs">{p.version}</td>
                <td className="px-4 py-2.5 text-slate-500">{p.module_type}</td>
                <td className="px-4 py-2.5 text-slate-500 text-xs">{p.runtime_type}</td>
                <td className="px-4 py-2.5"><StatusBadge status={p.status} /></td>
                <td className="px-4 py-2.5 text-slate-400 text-xs">
                  {new Date(p.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1 justify-end">
                    {p.status === 'draft' && (
                      <button
                        onClick={() => handleActivate(p.id, p.name)}
                        disabled={acting === p.id}
                        title="Activate"
                        className="p-1 rounded text-slate-300 hover:text-green-600 hover:bg-green-50 transition-colors disabled:opacity-40"
                      >
                        <CheckCircle size={14} />
                      </button>
                    )}
                    {p.status === 'active' && (
                      <button
                        onClick={() => handleDeprecate(p.id, p.name)}
                        disabled={acting === p.id}
                        title="Deprecate"
                        className="p-1 rounded text-slate-300 hover:text-orange-500 hover:bg-orange-50 transition-colors disabled:opacity-40"
                      >
                        <XCircle size={14} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(p.id, p.name)}
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
        <Modal title="New Plugin" onClose={() => { setShowAdd(false); setForm(EMPTY_FORM) }}>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input required autoFocus
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="my-function"
                  value={form.name} onChange={e => field('name', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Version</label>
                <input
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.version} onChange={e => field('version', e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Module type</label>
                <select
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.module_type} onChange={e => field('module_type', e.target.value)}>
                  <option value="function">function</option>
                  <option value="module">module</option>
                  <option value="service">service</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Runtime type</label>
                <select
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.runtime_type} onChange={e => field('runtime_type', e.target.value)}>
                  <option value="wasm-wasi">wasm-wasi</option>
                  <option value="docker">docker</option>
                  <option value="native">native</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Artifact URI <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://… or file:///…"
                value={form.artifact_uri} onChange={e => field('artifact_uri', e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Artifact checksum <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="sha256:…"
                value={form.artifact_checksum} onChange={e => field('artifact_checksum', e.target.value)} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Entrypoint</label>
                <input
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.entrypoint} onChange={e => field('entrypoint', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Timeout (s)</label>
                <input type="number" min={1} max={3600}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.timeout_seconds} onChange={e => field('timeout_seconds', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Memory (MB)</label>
                <input type="number" min={1} max={4096}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.memory_limit_mb} onChange={e => field('memory_limit_mb', e.target.value)} />
              </div>
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
                {form.submitting ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
