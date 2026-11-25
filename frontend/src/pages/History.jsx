import { ArrowRight, Clock, History as HistoryIcon, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useHistory } from '../context/HistoryContext.jsx'
import { formatDate, formatDuration } from '../utils/format'

export default function History() {
  const { items, removeEntry, clearHistory } = useHistory()

  const handleClear = () => {
    if (window.confirm('Clear all videos from this device’s history? Processed videos stay cached on the server.')) {
      clearHistory()
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="label text-accent-text">Library</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            Your processed videos
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            {items.length > 0
              ? `${items.length} ${items.length === 1 ? 'video' : 'videos'} on this device. Reopen any conversation with its index intact.`
              : 'Videos you process will appear here.'}
          </p>
        </div>

        {items.length > 0 && (
          <button type="button" onClick={handleClear} className="btn-ghost self-start text-xs">
            <Trash2 className="h-3.5 w-3.5" />
            Clear history
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="surface mt-8 flex flex-col items-center px-6 py-16 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-elevated text-muted">
            <HistoryIcon className="h-5 w-5" />
          </span>
          <h2 className="mt-4 text-base font-semibold text-fg">Nothing here yet</h2>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted">
            Paste a YouTube URL on the home page, then ask your first question. Processed videos
            show up here so you can return to them.
          </p>
          <Link to="/" className="btn-primary mt-6">
            Start a conversation
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <>
          <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => {
              const duration = formatDuration(item.duration_seconds)
              return (
                <article
                  key={item.video_id}
                  className="group surface overflow-hidden transition hover:border-line-strong"
                >
                  <Link to={`/chat/${item.video_id}`} className="block">
                    <div className="relative aspect-video overflow-hidden bg-elevated">
                      {item.thumbnail_url ? (
                        <img
                          src={item.thumbnail_url}
                          alt=""
                          loading="lazy"
                          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                          onError={(event) => {
                            event.currentTarget.style.visibility = 'hidden'
                          }}
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-subtle">
                          <HistoryIcon className="h-8 w-8" />
                        </div>
                      )}
                      {duration && (
                        <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded bg-black/80 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-white backdrop-blur">
                          <Clock className="h-3 w-3" />
                          {duration}
                        </span>
                      )}
                    </div>
                  </Link>

                  <div className="p-3.5">
                    <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-fg">
                      {item.title}
                    </h3>
                    <p className="mt-1 truncate text-xs text-subtle">
                      {[item.channel, formatDate(item.processed_at)].filter(Boolean).join(' · ')}
                    </p>

                    <div className="mt-3 flex gap-2">
                      <Link to={`/chat/${item.video_id}`} className="btn-ghost flex-1 py-1.5 text-xs">
                        Open chat
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                      <button
                        type="button"
                        onClick={() => removeEntry(item.video_id)}
                        aria-label={`Remove ${item.title} from history`}
                        title="Remove from history"
                        className="btn-ghost px-2.5 py-1.5 text-rose-500 hover:border-rose-500/40 hover:bg-rose-500/10"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>

          <p className="mt-6 text-xs leading-relaxed text-subtle">
            History is stored in this browser only. Video transcripts and embeddings stay cached on
            the server so reopening a video does not reprocess it.
          </p>
        </>
      )}
    </main>
  )
}
