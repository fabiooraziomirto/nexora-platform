interface Props { status: string }

const STYLES: Record<string, string> = {
  // device
  online:     'bg-green-100 text-green-800 border-green-200',
  offline:    'bg-red-100 text-red-800 border-red-200',
  unknown:    'bg-gray-100 text-gray-600 border-gray-200',
  // plugin
  active:     'bg-green-100 text-green-800 border-green-200',
  draft:      'bg-blue-100 text-blue-800 border-blue-200',
  inactive:   'bg-gray-100 text-gray-600 border-gray-200',
  deprecated: 'bg-orange-100 text-orange-800 border-orange-200',
  // execution
  queued:     'bg-blue-100 text-blue-800 border-blue-200',
  dispatched: 'bg-purple-100 text-purple-800 border-purple-200',
  running:    'bg-yellow-100 text-yellow-800 border-yellow-200',
  succeeded:  'bg-green-100 text-green-800 border-green-200',
  failed:     'bg-red-100 text-red-800 border-red-200',
  timeout:    'bg-orange-100 text-orange-800 border-orange-200',
  cancelled:  'bg-gray-100 text-gray-600 border-gray-200',
  // port
  created:    'bg-blue-100 text-blue-800 border-blue-200',
  attached:   'bg-green-100 text-green-800 border-green-200',
  detached:   'bg-gray-100 text-gray-600 border-gray-200',
  // webservice
  enabled:    'bg-green-100 text-green-800 border-green-200',
  disabled:   'bg-gray-100 text-gray-600 border-gray-200',
}

const DOT: Record<string, string> = {
  online: 'bg-green-500', offline: 'bg-red-500', unknown: 'bg-gray-400',
  active: 'bg-green-500', draft: 'bg-blue-500', inactive: 'bg-gray-400', deprecated: 'bg-orange-400',
  queued: 'bg-blue-500', dispatched: 'bg-purple-500', running: 'bg-yellow-500',
  succeeded: 'bg-green-500', failed: 'bg-red-500', timeout: 'bg-orange-400', cancelled: 'bg-gray-400',
  created: 'bg-blue-500', attached: 'bg-green-500', detached: 'bg-gray-400',
  enabled: 'bg-green-500', disabled: 'bg-gray-400',
}

export default function StatusBadge({ status }: Props) {
  const cls = STYLES[status] ?? STYLES.unknown
  const dot = DOT[status] ?? DOT.unknown
  return (
    <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium border ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  )
}
