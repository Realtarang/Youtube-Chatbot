import { AlertCircle, ChevronRight, Loader2, MessagesSquare, Sparkles, Trash2 } from 'lucide-react'
import { useEffect, useRef } from 'react'

import ChatInput from './ChatInput.jsx'
import ChatMessage from './ChatMessage.jsx'

const DEFAULT_QUESTIONS = [
  'Summarize this video in a few paragraphs.',
  'What are the key takeaways?',
  'What topics does this video cover?',
]

const DEPTHS = [
  { key: 'brief', label: 'Brief', hint: 'A couple of sentences' },
  { key: 'balanced', label: 'Balanced', hint: 'Short paragraphs with citations' },
  { key: 'deep', label: 'Deep dive', hint: 'Thorough, structured answer' },
]

function DepthSelector({ value, onChange, disabled }) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-line bg-elevated p-0.5">
      {DEPTHS.map((depth) => (
        <button
          key={depth.key}
          type="button"
          disabled={disabled}
          onClick={() => onChange(depth.key)}
          title={depth.hint}
          aria-pressed={value === depth.key}
          className={`rounded-md px-2 py-1 text-[11.5px] font-medium transition ${
            value === depth.key
              ? 'bg-surface text-fg shadow-sm'
              : 'text-muted hover:text-fg'
          } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          {depth.label}
        </button>
      ))}
    </div>
  )
}

export default function ChatWindow({
  video,
  messages,
  isLoading,
  isRestoring,
  error,
  onSend,
  onClear,
  onSeek,
  ready,
  followups = [],
  draft = '',
  onDraftHandled,
  detail = 'balanced',
  onDetailChange,
}) {
  const scrollRef = useRef(null)
  const suggestions =
    video?.suggested_questions?.length > 0 ? video.suggested_questions.slice(0, 5) : DEFAULT_QUESTIONS
  const lastMessage = messages[messages.length - 1]
  const degraded = Boolean(lastMessage?.degraded)

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages, isLoading, isRestoring])

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-elevated text-muted">
            <MessagesSquare className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <h2 className="text-[13px] font-semibold text-fg">Conversation</h2>
            <p className="truncate text-[11px] text-subtle">
              {ready && video?.chunk_count
                ? `${video.chunk_count} indexed passages · answers cite timestamps`
                : 'Answers grounded in the transcript'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClear}
          disabled={!messages.length || !ready}
          className="btn-ghost px-2.5 py-1.5 text-xs"
          title="Clear this conversation"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Clear</span>
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-3.5 py-4 sm:px-5">
        {!ready ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-accent" />
            <p className="text-sm font-medium text-fg">Indexing the transcript…</p>
            <p className="max-w-xs text-xs leading-relaxed text-muted">
              Chunking captions and generating embeddings. Chat unlocks automatically when the
              index is ready.
            </p>
          </div>
        ) : isRestoring ? (
          <div className="flex h-full items-center justify-center gap-2.5 text-sm text-subtle">
            <Loader2 className="h-4 w-4 animate-spin" />
            Restoring your conversation…
          </div>
        ) : messages.length === 0 ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-elevated p-5">
              <div className="mb-2 flex items-center gap-2 text-accent-text">
                <Sparkles className="h-4 w-4" />
                <span className="label text-accent-text">Ready</span>
              </div>
              <h3 className="text-[15px] font-semibold text-fg">Ask anything about this video</h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
                I search the transcript for the relevant moments, then answer using only what the
                video actually says — with timestamps you can jump to.
              </p>
            </div>

            <div className="space-y-2">
              <p className="label px-1">Suggested questions</p>
              {suggestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => onSend(question)}
                  disabled={isLoading}
                  className="group flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-elevated px-3.5 py-2.5 text-left text-[13.5px] text-body transition hover:border-accent/40 hover:text-fg disabled:opacity-50"
                >
                  <span>{question}</span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-subtle transition group-hover:text-accent-text" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} onSeek={onSeek} />
          ))
        )}

        {isLoading && (
          <div className="flex gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-accent/30 bg-accent-soft text-accent-text">
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <div className="flex items-center gap-2 rounded-xl rounded-tl-sm border border-line bg-surface px-4 py-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
              <span className="ml-1 text-xs text-subtle">Searching the transcript…</span>
            </div>
          </div>
        )}
      </div>

      {degraded && (
        <div className="mx-3 mb-2 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.08] px-3 py-2 text-[11.5px] leading-relaxed text-amber-700 dark:text-amber-200/90 sm:mx-4">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            The AI service was unavailable, so this reply quotes the transcript directly. Ask again
            in a moment for a written answer.
          </span>
        </div>
      )}

      {error && (
        <div className="mx-3 mb-2 flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/[0.08] px-3 py-2 text-xs text-rose-600 dark:text-rose-300 sm:mx-4">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {ready && followups.length > 0 && !isLoading && messages.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-line px-3 pt-2.5 sm:px-4">
          <span className="label self-center text-[10px]">Next</span>
          {followups.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => onSend(question)}
              className="rounded-full border border-line bg-elevated px-2.5 py-1 text-[11.5px] text-muted transition hover:border-accent/40 hover:text-fg"
            >
              {question}
            </button>
          ))}
        </div>
      )}

      {ready && (
        <div className="flex items-center justify-between gap-3 border-t border-line px-3 pt-2 sm:px-4">
          <span className="label text-[10px]">Answer depth</span>
          <DepthSelector value={detail} onChange={onDetailChange} disabled={isLoading} />
        </div>
      )}

      {ready && (
        <ChatInput
          onSend={onSend}
          disabled={!ready || isLoading}
          loading={isLoading}
          draft={draft}
          onDraftHandled={onDraftHandled}
          placeholder={isLoading ? 'Waiting for the answer…' : 'Ask a question about this video…'}
        />
      )}
    </section>
  )
}
