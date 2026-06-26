import { useState } from 'react'
import { RefreshCw, Plus, Trash2, Terminal, Play, X as XIcon, ChevronDown, ChevronUp } from 'lucide-react'
import { api, type ExecutionCreate } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import { SkeletonRows } from '../components/Skeleton'

interface FormState extends ExecutionCreate { submitting: boolean; error: string; args_raw: string }

const EMPTY_FORM: FormState = {
  device_id: '', execution_type: 'command', command: '', plugin_id: '',
  args_raw: '', submitting: false, error: '',
}

const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'timeout', 'cancelled'])

export default function Executions() {
  const [filterDevice, setFilterDevice] = useState('')
  const { data, loading, error, reload } = useApi(
    () => api.listExecutions(1, 200, filterDevice || undefined),
    [filterDevice],
  )
  const [showAdd, setShowAdd]   = useState(false)
  const [form, setForm]         = useState<FormState>(EMPTY_FORM)
  const [acting, setActing]     = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const toast = useToast()

  const executions = data?.items ?? []

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setForm(f => ({ ...f, submitting: true, error: '' }))
    let args: Record<string, unknown> | undefined
    if (form.args_raw.trim()) {
      try { args = JSON.parse(form.args_raw) } catch {
        setForm(f => ({ ...f, submitting: false, error: 'Args must be valid JSON' }))
        return
      }
    }
    try {
      const body: ExecutionCreate = {
        device_id: form.device_id.trim(),
        execution_type: form.execution_type,
        command: form.command.trim(),
        ...((form.plugin_id ?? '').trim() && { plugin_id: (form.plugin_id ?? '').trim() }),
        ...(args && { args }),
      }
      const ex = await api.createExecution(body)
      setShowAdd(false)
      setForm(EMPTY_FORM)
      reload()
      toast.show('success', 'Execution created', `ID: ${ex.id}`)
    } catch (err) {
      setForm(f => ({ ...f, submitting: false, error: String(err) }))
    }
  }

  async function handleDispatch(id: string) {
    setActing(id)
    try {
      await api.dispatchExecution(id)
      reload()
      toast.show('success', 'Execution dispatched')
    } catch {
      toast.show('error', 'Failed to dispatch execution')
    } finally {
      setActing(null)
    }
  }

  async function handleCancel(id: string) {
    setActing(id)
    try {
      await api.cancelExecution(id)
      reload()
      toast.show('info', 'Execution cancelled')
    } catch {
      toast.show('error', 'Failed to cancel execution')
    } finally {
      setActing(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this execution record?')) return
    setActing(id)
    try {
      await api.deleteExecution(id)
      reload()
      toast.show('success', 'Execution deleted')
    } catch {
      toast.show('error', 'Failed to delete execution')
    } finally {
      setActing(null)
    }
  }

  function setExecType(t: string) {
    const cmd = t === 'function.install' ? 'function.install:' : t === 'function.invoke' ? 'function.invoke:' : ''
    setForm(f => ({ ...f, execution_type: t, command: cmd }))
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Executions</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} total` : loading ? '…' : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="border border-slate-300 rounded px-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
            placeholder="Filter by device ID…"
            value={filterDevice}
            onChange={e => setFilterDevice(e.target.value)}
          />
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
            New Execution
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
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide w-8" />
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Device</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Command</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Exit</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">Created</th>
              <th className="px-4 py-2.5 w-24" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && !data ? (
              <SkeletonRows rows={5} cols={8} />
            ) : executions.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <div className="flex flex-col items-center py-14 text-slate-400">
                    <Terminal size={32} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">No executions found</p>
                  </div>
                </td>
              </tr>
            ) : executions.map(ex => (
              <>
                <tr key={ex.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-2.5">
                    {(ex.result_stdout || ex.result_stderr || ex.function_result != null) && (
                      <button
                        onClick={() => setExpanded(e => e === ex.id ? null : ex.id)}
                        className="p-0.5 text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        {expanded === ex.id ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[140px] truncate" title={ex.device_id}>
                    {ex.device_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2.5 text-slate-700 font-mono text-xs max-w-[200px] truncate" title={ex.command}>
                    {ex.command}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">{ex.execution_type}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={ex.status} /></td>
                  <td className="px-4 py-2.5 text-slate-500 font-mono text-xs">
                    {ex.exit_code !== null ? ex.exit_code : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 text-xs">
                    {new Date(ex.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1 justify-end">
                      {ex.status === 'queued' && (
                        <button
                          onClick={() => handleDispatch(ex.id)}
                          disabled={acting === ex.id}
                          title="Dispatch"
                          className="p-1 rounded text-slate-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40"
                        >
                          <Play size={13} />
                        </button>
                      )}
                      {(ex.status === 'dispatched' || ex.status === 'running') && (
                        <button
                          onClick={() => handleCancel(ex.id)}
                          disabled={acting === ex.id}
                          title="Cancel"
                          className="p-1 rounded text-slate-300 hover:text-orange-500 hover:bg-orange-50 transition-colors disabled:opacity-40"
                        >
                          <XIcon size={13} />
                        </button>
                      )}
                      {TERMINAL_STATUSES.has(ex.status) && (
                        <button
                          onClick={() => handleDelete(ex.id)}
                          disabled={acting === ex.id}
                          title="Delete"
                          className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {expanded === ex.id && (
                  <tr key={`${ex.id}-detail`} className="bg-slate-50">
                    <td colSpan={8} className="px-8 py-3">
                      {ex.result_stdout && (
                        <div className="mb-2">
                          <p className="text-xs font-medium text-slate-500 mb-1">stdout</p>
                          <pre className="text-xs bg-white border border-slate-200 rounded px-3 py-2 overflow-auto max-h-32 text-slate-700 whitespace-pre-wrap">{ex.result_stdout}</pre>
                        </div>
                      )}
                      {ex.result_stderr && (
                        <div className="mb-2">
                          <p className="text-xs font-medium text-slate-500 mb-1">stderr</p>
                          <pre className="text-xs bg-white border border-red-200 rounded px-3 py-2 overflow-auto max-h-32 text-red-700 whitespace-pre-wrap">{ex.result_stderr}</pre>
                        </div>
                      )}
                      {ex.function_result !== null && ex.function_result !== undefined && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 mb-1">function_result</p>
                          <pre className="text-xs bg-white border border-slate-200 rounded px-3 py-2 overflow-auto max-h-32 text-slate-700 whitespace-pre-wrap">{JSON.stringify(ex.function_result as Record<string, unknown>, null, 2)}</pre>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <Modal title="New Execution" onClose={() => { setShowAdd(false); setForm(EMPTY_FORM) }}>
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
              <label className="block text-xs font-medium text-slate-700 mb-1">Execution type</label>
              <select
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.execution_type} onChange={e => setExecType(e.target.value)}>
                <option value="command">command</option>
                <option value="function.install">function.install</option>
                <option value="function.invoke">function.invoke</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Command <span className="text-red-500">*</span>
              </label>
              <input required
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder={form.execution_type === 'command' ? 'echo hello' : `${form.execution_type}:<plugin-id>`}
                value={form.command} onChange={e => setForm(f => ({ ...f, command: e.target.value }))} />
            </div>
            {form.execution_type !== 'command' && (
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Plugin ID</label>
                <input
                  className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="uuid"
                  value={form.plugin_id} onChange={e => setForm(f => ({ ...f, plugin_id: e.target.value }))} />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Args (JSON)</label>
              <textarea rows={2}
                className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder='{"key": "value"}'
                value={form.args_raw} onChange={e => setForm(f => ({ ...f, args_raw: e.target.value }))} />
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
