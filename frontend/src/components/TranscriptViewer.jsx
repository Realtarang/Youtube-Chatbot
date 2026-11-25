import { AlertCircle, FileText, Loader2, MessageSquarePlus, Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import SlideOver from './SlideOver.jsx'
import TimestampLink from './TimestampLink.jsx'
import { formatTimestamp } from '../utils/format'

const PAGE_SIZE = 250

function highlight(text, query) {
  if (!query) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
  return parts.map((part, index) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={index} className="rounded bg-accent-soft px-0.5 text-fg">
        {part}
      </mark>
    ) : (
      <span key={index}>{part}</span>
    ),
  )
}

export default function TranscriptViewer({
  open,
  onClose,
  transcript,
  loading,
  error,
  onSeek,
  onAskAboutMoment,
  activeSeconds,
}) {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const listRef = useRef(null)

  const segments = transcript?.segments || []

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return segments
    return segments.filter((segment) => segment.text.toLowerCase().includes(needle))
  }, [segments, query])

  useEffect(() => {
    setLimit(PAGE_SIZE)
  }, [query, transcript?.video_id])

  useEffect(() => {
    if (!open || activeSeconds === null || activeSeconds === undefined) return
    const node = listRef.current?.querySelector('[data-active="true"]')
    node?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [activeSeconds, open])

  useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  const activeIndex = useMemo(() => {
    if (activeSeconds === null || activeSeconds === undefined) return -1
    return segments.findIndex(
      (segment) => activeSeconds >= segment.start && activeSeconds < segment.end,
    )
  }, [segments, activeSeconds])

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Full transcript"
      subtitle={
        transcript
          ? `${segments.length} cues${transcript.language ? ` · ${transcript.language.toUpperCase()}` : ''}`
          : 'Extracted captions with timestamps'
      }
      icon={FileText}
    >
      <div className="border-b border-line bg-surface p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search within the transcript…"
            className="field py-2 pl-9 pr-9 text-sm"
            aria-label="Search transcript"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-subtle transition hover:bg-elevated hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <p className="mt-2 px-1 text-[11px] text-subtle">
          {query
            ? `${filtered.length} matching ${filtered.length === 1 ? 'cue' : 'cues'}`
            : 'Click a timestamp to jump to that moment, or ask about it in the chat.'}
        </p>
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center gap-2.5 py-16 text-sm text-subtle">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading transcript…
          </div>
        )}

        {error && !loading && (
          <div className="m-4 flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/[0.08] px-3.5 py-3 text-sm text-rose-600 dark:text-rose-300">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <p className="px-5 py-16 text-center text-sm text-subtle">
            No transcript cues match “{query}”.
          </p>
        )}

        {!loading &&
          !error &&
          filtered.slice(0, limit).map((segment, index) => {
            const isActive = activeIndex >= 0 && segments[activeIndex] === segment
            return (
              <div
                key={`${segment.start}-${index}`}
                data-active={isActive ? 'true' : 'false'}
                className={`group flex gap-3 border-b border-line/70 px-4 py-2.5 transition ${
                  isActive ? 'bg-accent-soft' : 'hover:bg-elevated'
                }`}
              >
                <TimestampLink
                  seconds={segment.start}
                  onSeek={onSeek}
                  className="mt-0.5 shrink-0"
                  hint={`Seek to ${formatTimestamp(segment.start)}`}
                />
                <p className="flex-1 text-[13px] leading-relaxed text-body">
                  {highlight(segment.text, query.trim())}
                </p>
                {onAskAboutMoment && (
                  <button
                    type="button"
                    onClick={() => onAskAboutMoment(segment)}
                    title="Ask the chat about this moment"
                    className="mt-0.5 hidden h-6 w-6 shrink-0 items-center justify-center rounded border border-line text-subtle transition hover:border-accent/40 hover:text-accent-text group-hover:flex"
                  >
                    <MessageSquarePlus className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )
          })}

        {!loading && !error && filtered.length > limit && (
          <div className="p-4">
            <button
              type="button"
              onClick={() => setLimit((previous) => previous + PAGE_SIZE)}
              className="btn-ghost w-full text-xs"
            >
              Show {Math.min(PAGE_SIZE, filtered.length - limit)} more cues
            </button>
          </div>
        )}
      </div>
    </SlideOver>
  )
}
