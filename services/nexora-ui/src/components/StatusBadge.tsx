interface Props { status: string }

const COLORS: Record<string, string> = {
  online:  'bg-green-500/15 text-green-400 ring-green-500/30',
  offline: 'bg-red-500/15 text-red-400 ring-red-500/30',
  unknown: 'bg-gray-500/15 text-gray-400 ring-gray-500/30',
}

export default function StatusBadge({ status }: Props) {
  const cls = COLORS[status] ?? COLORS.unknown
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  )
}
