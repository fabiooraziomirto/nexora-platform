import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const auth = useAuth()
  const configured = Boolean(import.meta.env.VITE_KEYCLOAK_URL)

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white border border-slate-200 rounded p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-5">
          <div className="h-9 w-9 rounded bg-blue-600 text-white flex items-center justify-center">
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-900">Nexora</h1>
            <p className="text-xs text-slate-500">Enterprise access</p>
          </div>
        </div>
        {!configured && (
          <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Keycloak is not configured for this UI build.
          </div>
        )}
        <button
          onClick={() => auth.login()}
          disabled={!configured}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600"
        >
          Sign in with Keycloak
        </button>
      </div>
    </div>
  )
}
