import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, CheckCircle2, Circle, PlayCircle, ShieldCheck } from 'lucide-react'
import { api, type PendingDiscovery } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/Toast'

const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'timeout', 'cancelled'])

export default function OnboardingWizard() {
  const [pending, setPending] = useState<PendingDiscovery[]>([])
  const [loadingPending, setLoadingPending] = useState(false)
  const [selectedDiscoveryId, setSelectedDiscoveryId] = useState('')
  const [approvalName, setApprovalName] = useState('')
  const [approvedDeviceId, setApprovedDeviceId] = useState('')
  const [command, setCommand] = useState('echo onboarding-ok')
  const [executionId, setExecutionId] = useState('')
  const [executionStatus, setExecutionStatus] = useState('')
  const [acting, setActing] = useState(false)

  const auth = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const selectedPending = useMemo(
    () => pending.find(d => d.discovery_id === selectedDiscoveryId) ?? null,
    [pending, selectedDiscoveryId],
  )

  const writePermissionHint = 'Write permission required (operator, tenant-admin, or platform-admin)'

  const step1Done = pending.length > 0 && Boolean(selectedDiscoveryId)
  const step2Done = Boolean(approvedDeviceId)
  const step3Done = Boolean(executionId)
  const step4Done = TERMINAL_STATUSES.has(executionStatus)

  async function loadPending() {
    setLoadingPending(true)
    try {
      const items = await api.listPendingDevices()
      setPending(items)
      if (!selectedDiscoveryId && items.length > 0) {
        setSelectedDiscoveryId(items[0].discovery_id)
        setApprovalName(`device-${items[0].hardware_id.slice(-6)}`)
      }
    } catch (err) {
      toast.show('error', 'Unable to load pending devices', String(err))
    } finally {
      setLoadingPending(false)
    }
  }

  useEffect(() => {
    loadPending()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selectedPending) return
    if (!approvalName.trim()) {
      setApprovalName(`device-${selectedPending.hardware_id.slice(-6)}`)
    }
  }, [selectedPending, approvalName])

  useEffect(() => {
    if (!executionId) return

    const timer = window.setInterval(async () => {
      try {
        const ex = await api.getExecution(executionId)
        setExecutionStatus(ex.status)
        if (TERMINAL_STATUSES.has(ex.status)) {
          window.clearInterval(timer)
        }
      } catch {
        // Keep polling silently; transient failures should not break the wizard flow.
      }
    }, 1500)

    return () => window.clearInterval(timer)
  }, [executionId])

  async function approvePending() {
    if (!selectedPending) {
      toast.show('info', 'Select a pending device first')
      return
    }
    if (!approvalName.trim()) {
      toast.show('info', 'Enter a device name to approve')
      return
    }

    setActing(true)
    try {
      const result = await api.claimPendingDevice(selectedPending.discovery_id, { name: approvalName.trim() })
      setApprovedDeviceId(result.device_id)
      setPending(curr => curr.filter(p => p.discovery_id !== selectedPending.discovery_id))
      setSelectedDiscoveryId('')
      toast.show('success', 'Device approved', `New device id: ${result.device_id}`)
    } catch (err) {
      toast.show('error', 'Failed to approve pending device', String(err))
    } finally {
      setActing(false)
    }
  }

  async function runFirstCommand() {
    if (!approvedDeviceId) {
      toast.show('info', 'Approve a device first')
      return
    }

    setActing(true)
    try {
      const created = await api.createExecution({
        device_id: approvedDeviceId,
        execution_type: 'command',
        command: command.trim() || 'echo onboarding-ok',
      })
      await api.dispatchExecution(created.id)
      setExecutionId(created.id)
      setExecutionStatus('dispatched')
      toast.show('success', 'First command dispatched', `Execution: ${created.id}`)
    } catch (err) {
      toast.show('error', 'Failed to dispatch first command', String(err))
    } finally {
      setActing(false)
    }
  }

  function Step({ done, title, detail }: { done: boolean; title: string; detail: string }) {
    return (
      <div className="flex items-start gap-3 rounded border border-slate-200 bg-white px-4 py-3">
        {done ? <CheckCircle2 className="mt-0.5 text-emerald-600" size={18} /> : <Circle className="mt-0.5 text-slate-300" size={18} />}
        <div>
          <p className="text-sm font-medium text-slate-900">{title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{detail}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Onboarding Wizard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Pair / Approve / Execute / Verify in one guided flow.</p>
        </div>
        <button
          onClick={loadPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw size={14} className={loadingPending ? 'animate-spin' : ''} />
          Refresh Pending
        </button>
      </div>

      {!auth.canWrite && (
        <div className="rounded border border-indigo-200 bg-indigo-50 text-indigo-800 text-sm px-4 py-2.5">
          Read-only mode: onboarding actions are disabled for your role. {writePermissionHint}.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-3">
          <Step done={step1Done} title="1. Pending device selected" detail="Select a pending pairing request from discovery queue." />
          <Step done={step2Done} title="2. Device approved" detail="Approve selected pending device with production-ready name." />
          <Step done={step3Done} title="3. First command dispatched" detail="Run first command to prove control-plane delivery." />
          <Step done={step4Done} title="4. Result verified" detail="Execution reached terminal status and can be audited." />
        </div>

        <div className="rounded border border-slate-200 bg-white p-4 space-y-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Pending Discovery</p>
            <select
              value={selectedDiscoveryId}
              onChange={(e) => {
                const value = e.target.value
                setSelectedDiscoveryId(value)
                const item = pending.find(p => p.discovery_id === value)
                if (item) setApprovalName(`device-${item.hardware_id.slice(-6)}`)
              }}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            >
              <option value="">{loadingPending ? 'Loading…' : pending.length === 0 ? 'No pending devices' : 'Select pending device'}</option>
              {pending.map((d) => (
                <option key={d.discovery_id} value={d.discovery_id}>
                  {d.user_code} | {d.hardware_id} | {d.device_type}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Approved Device Name</label>
            <input
              value={approvalName}
              onChange={(e) => setApprovalName(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              placeholder="device-floor-01"
            />
          </div>

          <button
            onClick={approvePending}
            disabled={!auth.canWrite || acting || !selectedPending}
            title={!auth.canWrite ? writePermissionHint : undefined}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            <ShieldCheck size={15} />
            Approve Device
          </button>

          <div className="pt-2 border-t border-slate-100">
            <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">First Command</label>
            <input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
              placeholder="echo onboarding-ok"
            />
            <button
              onClick={runFirstCommand}
              disabled={!auth.canWrite || acting || !approvedDeviceId}
              title={!auth.canWrite ? writePermissionHint : undefined}
              className="mt-2 inline-flex items-center gap-1.5 px-3 py-2 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              <PlayCircle size={15} />
              Dispatch First Command
            </button>
          </div>

          <div className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 space-y-1">
            <p>approved_device_id: <span className="font-mono">{approvedDeviceId || '—'}</span></p>
            <p>execution_id: <span className="font-mono">{executionId || '—'}</span></p>
            <p>execution_status: <span className="font-semibold">{executionStatus || '—'}</span></p>
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => navigate('/devices')} className="px-3 py-1.5 rounded border border-slate-300 text-xs hover:bg-slate-50">Open Devices</button>
            <button onClick={() => navigate('/executions')} className="px-3 py-1.5 rounded border border-slate-300 text-xs hover:bg-slate-50">Open Executions</button>
            <button onClick={() => navigate('/audit')} className="px-3 py-1.5 rounded border border-slate-300 text-xs hover:bg-slate-50">Open Audit</button>
          </div>
        </div>
      </div>
    </div>
  )
}
