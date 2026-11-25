import { Play } from 'lucide-react'

import { formatTimestamp } from '../utils/format'

export default function TimestampLink({
  seconds,
  label,
  onSeek,
  hint,
  className = '',
}) {
  const text = label || formatTimestamp(seconds)

  return (
    <button
      type="button"
      onClick={() => onSeek?.(Number(seconds) || 0)}
      title={hint || `Jump to ${text} in the video`}
      className={`inline-flex items-center gap-1 rounded border border-line bg-elevated px-1.5 py-0.5 font-mono text-[11px] font-medium tabular-nums text-muted transition hover:border-accent/40 hover:text-accent-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${className}`}
    >
      <Play className="h-2.5 w-2.5 fill-current" />
      {text}
    </button>
  )
}
