import { Loader2, Search, X } from 'lucide-react'
import { useState } from 'react'

import { getErrorMessage, searchVideo } from '../services/api'

/**
 * Semantic search over one video: returns the transcript moments that match a
 * natural-language query and seeks the player when a result is clicked.
 */
export default function FindMoments({ videoId, onSeek, disabled = false }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const reset = () => {
    setQuery('')
    setResults(null)
    setError('')
  }

  const submit = async (event) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setError('Type at least two characters.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await searchVideo(videoId, trimmed)
      setResults(data.results || [])
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="surface p-3">
      <form onSubmit={submit} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find a moment in this video…"
            aria-label="Search inside the video"
            disabled={disabled}
            className="field py-2 pl-8 pr-8 text-[13px]"
          />
          {(query || results) && (
            <button
              type="button"
              onClick={reset}
              aria-label="Clear search"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-subtle transition hover:bg-elevated hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <button
          type="submit"
          disabled={disabled || loading}
          className="btn-ghost px-2.5 py-2 text-xs"
          title="Search the transcript"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
        </button>
      </form>

      {error && <p className="mt-2 text-[11.5px] text-rose-600 dark:text-rose-300">{error}</p>}

      {results && !loading && (
        <div className="mt-2.5">
          <p className="label text-[10px]">
            {results.length === 0 ? 'No matching moments' : `${results.length} matching moments`}
          </p>
          <div className="mt-1.5 max-h-64 space-y-1.5 overflow-y-auto pr-0.5">
            {results.map((result) => (
              <button
                key={`${result.chunk_index}-${result.start_time}`}
                type="button"
                onClick={() => onSeek?.(result.start_time)}
                className="w-full rounded-lg border border-line bg-elevated p-2 text-left transition hover:border-accent/40"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10.5px] font-medium tabular-nums text-accent-text">
                    {result.timestamp}
                  </span>
                  <span className="h-1 w-10 overflow-hidden rounded-full bg-line">
                    <span
                      className="block h-full rounded-full bg-accent"
                      style={{ width: `${Math.max(12, Math.min(100, Math.round(result.score * 100)))}%` }}
                    />
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[11.5px] leading-snug text-muted">
                  {result.snippet}
                </p>
              </button>
            ))}
          </div>
          {results.length === 0 && (
            <p className="mt-1 text-[11px] leading-relaxed text-subtle">
              Try different words, or ask the chat instead.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
