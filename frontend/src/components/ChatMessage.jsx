import { Check, Copy, Sparkles, User } from 'lucide-react'
import { useRef, useState } from 'react'

import TimestampLink from './TimestampLink.jsx'
import { formatTimestamp } from '../utils/format'

const INLINE_RE = /(\*\*[^*]+\*\*|\[\d{1,2}(?::\d{2}){1,2}\])/g
const BULLET_RE = /^[-*•]\s+/
const HEADING_RE = /^#{1,6}\s+/

const stampToSeconds = (stamp) =>
  stamp.split(':').reduce((total, part) => total * 60 + Number(part), 0)

function renderInline(text, onSeek) {
  return text.split(INLINE_RE).filter(Boolean).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={index} className="font-semibold text-fg">
          {part.slice(2, -2)}
        </strong>
      )
    }
    const stamp = /^\[(\d{1,2}(?::\d{2}){1,2})\]$/.exec(part)
    if (stamp) {
      return (
        <TimestampLink
          key={index}
          label={stamp[1]}
          seconds={stampToSeconds(stamp[1])}
          onSeek={onSeek}
          className="mx-0.5 align-baseline"
        />
      )
    }
    return <span key={index}>{part}</span>
  })
}

function AnswerBody({ text, onSeek }) {
  return (
    <div className="space-y-1.5">
      {text.split('\n').map((line, index) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={index} className="h-0.5" />
        if (HEADING_RE.test(trimmed)) {
          return (
            <p key={index} className="pt-1 font-semibold text-fg">
              {renderInline(trimmed.replace(HEADING_RE, ''), onSeek)}
            </p>
          )
        }
        if (BULLET_RE.test(trimmed)) {
          return (
            <p key={index} className="flex gap-2 pl-0.5">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-subtle" />
              <span>{renderInline(trimmed.replace(BULLET_RE, ''), onSeek)}</span>
            </p>
          )
        }
        return <p key={index}>{renderInline(trimmed, onSeek)}</p>
      })}
    </div>
  )
}

export default function ChatMessage({ message, onSeek }) {
  const isUser = message.role === 'user'
  const sources = message.sources || []
  const [copied, setCopied] = useState(false)
  const timer = useRef(null)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard permissions can be denied; the text stays selectable.
    }
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} animate-fade-up`}>
      <div
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
          isUser
            ? 'border-line bg-elevated text-muted'
            : 'border-accent/30 bg-accent-soft text-accent-text'
        }`}
      >
        {isUser ? <User className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
      </div>

      <div className={`group min-w-0 max-w-[86%] ${isUser ? '' : 'w-full sm:max-w-[88%]'}`}>
        <div
          className={`rounded-xl px-4 py-3 text-[14.5px] leading-relaxed ${
            isUser
              ? 'rounded-tr-sm border border-line bg-elevated text-fg'
              : 'rounded-tl-sm border border-line bg-surface text-body'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <AnswerBody text={message.content} onSeek={onSeek} />
          )}

          {sources.length > 0 && (
            <div className="mt-3.5 border-t border-line pt-3">
              <p className="label text-[10px]">
                Grounded in {sources.length} passage{sources.length === 1 ? '' : 's'}
              </p>
              <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                {sources.map((source) => (
                  <button
                    key={`${source.chunk_index}-${source.start_time}`}
                    type="button"
                    onClick={() => onSeek?.(source.start_time)}
                    title={`Jump to ${formatTimestamp(source.start_time)} in the video`}
                    className="rounded-lg border border-line bg-elevated p-2 text-left transition hover:border-accent/40"
                  >
                    <span className="font-mono text-[10.5px] font-medium tabular-nums text-accent-text">
                      {source.timestamp}
                    </span>
                    <span className="mt-1 line-clamp-2 block text-[11.5px] leading-snug text-muted">
                      {source.snippet}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {!isUser && (
          <div className="mt-1.5 flex items-center gap-2 px-1">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-subtle opacity-0 transition hover:bg-elevated hover:text-fg focus-visible:opacity-100 group-hover:opacity-100"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
              {copied ? 'Copied' : 'Copy answer'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
