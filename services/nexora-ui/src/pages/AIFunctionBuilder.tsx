import { useState } from 'react'
import { Code2, RefreshCw, Wand2 } from 'lucide-react'
import { api, type AIFunctionDraft } from '../api/client'
import { useToast } from '../components/Toast'

const INPUT = 'border border-slate-300 rounded bg-white px-3 py-1.5 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

export default function AIFunctionBuilder() {
  const [prompt, setPrompt] = useState('Alert when temperature is greater than 80')
  const [candidateIds, setCandidateIds] = useState('')
  const [draft, setDraft] = useState<AIFunctionDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  async function createDraft() {
    setLoading(true)
    try {
      const next = await api.createFunctionDraft({ prompt })
      setDraft(next)
      toast.show('success', 'Function draft created')
    } catch {
      toast.show('error', 'Failed to create function draft')
    } finally {
      setLoading(false)
    }
  }

  async function reviewDraft() {
    if (!draft) return
    setLoading(true)
    try {
      setDraft(await api.reviewFunctionDraft(draft.id))
      toast.show('success', 'Draft reviewed')
    } catch {
      toast.show('error', 'Failed to review draft')
    } finally {
      setLoading(false)
    }
  }

  async function calculatePlacement() {
    if (!draft) return
    const ids = candidateIds.split(',').map(v => v.trim()).filter(Boolean)
    setLoading(true)
    try {
      const placement = await api.calculateFunctionPlacement(draft.id, ids)
      setDraft({ ...draft, placement_result: placement })
      toast.show('success', 'Placement calculated')
    } catch {
      toast.show('error', 'Failed to calculate placement')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">AI Function Builder</h1>
          <p className="text-sm text-slate-500 mt-0.5">Generate AssemblyScript drafts and placement advice</p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded p-5 mb-5">
        <label className="block text-xs font-medium text-slate-700 mb-1">Function intent</label>
        <textarea className={`${INPUT} w-full min-h-24`} value={prompt} onChange={e => setPrompt(e.target.value)} />
        <div className="mt-3 flex gap-2">
          <button onClick={createDraft} disabled={loading || prompt.trim().length < 5} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-40">
            <Wand2 size={14} />
            Create Draft
          </button>
          <button onClick={reviewDraft} disabled={loading || !draft} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
            Review
          </button>
        </div>
      </div>

      {!draft ? (
        <div className="bg-white border border-slate-200 rounded py-20 flex flex-col items-center text-slate-400">
          <Code2 size={36} className="mb-3 opacity-30" />
          <p className="text-sm font-medium">No function draft yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-5">
          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">{draft.function_name}</h2>
              <p className="text-xs text-slate-500 mt-0.5">{draft.language} / status {draft.status}</p>
            </div>
            <pre className="m-0 max-h-[620px] overflow-auto bg-slate-950 p-4 text-xs leading-5 text-slate-100">{draft.source_code}</pre>
          </div>

          <aside className="space-y-5">
            <div className="bg-white border border-slate-200 rounded p-4">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Plugin Metadata</h3>
              <pre className="overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(draft.plugin_metadata, null, 2)}</pre>
            </div>
            <div className="bg-white border border-slate-200 rounded p-4">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Review</h3>
              <ul className="space-y-2 text-sm text-slate-700">
                {(draft.review.notes ?? []).map((note, index) => <li key={index}>{note}</li>)}
              </ul>
            </div>
            <div className="bg-white border border-slate-200 rounded p-4">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Placement</h3>
              <input className={`${INPUT} w-full mb-3`} placeholder="device-id-1, device-id-2" value={candidateIds} onChange={e => setCandidateIds(e.target.value)} />
              <button onClick={calculatePlacement} disabled={loading || !candidateIds.trim()} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                Calculate
              </button>
              {draft.placement_result && (
                <div className="mt-3 space-y-3">
                  <div>
                    <div className="text-xs font-medium text-slate-500 mb-1">Recommended</div>
                    {(draft.placement_result.recommended_targets ?? []).map(item => (
                      <div key={item.device_id} className="rounded border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800 mb-2">
                        {item.device_id} / score {item.score}: {item.reason}
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-500 mb-1">Avoid</div>
                    {(draft.placement_result.avoid_targets ?? []).map(item => (
                      <div key={item.device_id} className="rounded border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-800 mb-2">
                        {item.device_id} / score {item.score}: {item.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}
