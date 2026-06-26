export function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3.5 bg-slate-100 rounded animate-pulse" style={{ width: i === 0 ? '60%' : '40%' }} />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonRows({ rows, cols }: { rows: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} cols={cols} />
      ))}
    </>
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-white border border-slate-200 rounded p-4 space-y-2">
      <div className="h-3 bg-slate-100 rounded animate-pulse w-1/2" />
      <div className="h-6 bg-slate-100 rounded animate-pulse w-1/3" />
      <div className="h-2.5 bg-slate-100 rounded animate-pulse w-2/3" />
    </div>
  )
}
