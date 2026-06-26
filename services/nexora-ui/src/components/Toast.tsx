import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { CheckCircle, XCircle, Info, X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  type: ToastType
  message: string
  detail?: string
}

interface ToastCtx {
  show: (type: ToastType, message: string, detail?: string) => void
}

const Ctx = createContext<ToastCtx>({ show: () => {} })

let _id = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts(t => t.filter(x => x.id !== id))
  }, [])

  const show = useCallback((type: ToastType, message: string, detail?: string) => {
    const id = ++_id
    setToasts(t => [...t, { id, type, message, detail }])
    setTimeout(() => dismiss(id), type === 'error' ? 6000 : 3500)
  }, [dismiss])

  const ICON = { success: CheckCircle, error: XCircle, info: Info }
  const STYLE = {
    success: 'border-green-200 bg-green-50 text-green-800',
    error:   'border-red-200 bg-red-50 text-red-800',
    info:    'border-blue-200 bg-blue-50 text-blue-800',
  }
  const ICON_COLOR = { success: 'text-green-500', error: 'text-red-500', info: 'text-blue-500' }

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-80">
        {toasts.map(t => {
          const Icon = ICON[t.type]
          return (
            <div key={t.id} className={`flex items-start gap-3 rounded border px-3.5 py-3 shadow-md ${STYLE[t.type]}`}>
              <Icon size={16} className={`mt-0.5 shrink-0 ${ICON_COLOR[t.type]}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-snug">{t.message}</p>
                {t.detail && <p className="text-xs mt-0.5 opacity-70 break-all">{t.detail}</p>}
              </div>
              <button onClick={() => dismiss(t.id)} className="shrink-0 opacity-50 hover:opacity-80 transition-opacity">
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}

export function useToast() {
  return useContext(Ctx)
}
