import { AlertCircle, ArrowRight, Loader2, Youtube } from 'lucide-react'
import { useState } from 'react'

const YOUTUBE_URL_RE =
  /^(https?:\/\/)?(www\.|m\.|music\.)?(youtube\.com\/(watch\?(?:.*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)[\w-]{11}/

export default function VideoInput({ onSubmit, loading = false, error = '', autoFocus = false }) {
  const [url, setUrl] = useState('')
  const [localError, setLocalError] = useState('')

  const handleSubmit = (event) => {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) {
      setLocalError('Paste a YouTube video URL first.')
      return
    }
    if (!YOUTUBE_URL_RE.test(trimmed)) {
      setLocalError('That is not a recognised YouTube link. Try a youtube.com/watch or youtu.be URL.')
      return
    }
    setLocalError('')
    onSubmit(trimmed)
  }

  const message = localError || error

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex flex-col gap-2.5 sm:flex-row">
        <div className="relative flex-1">
          <Youtube className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-red-500/70" />
          <input
            type="text"
            value={url}
            autoFocus={autoFocus}
            onChange={(event) => {
              setUrl(event.target.value)
              if (localError) setLocalError('')
            }}
            placeholder="https://www.youtube.com/watch?v=..."
            aria-label="YouTube video URL"
            spellCheck="false"
            className="field h-[48px] pl-10 pr-4 text-[14.5px]"
          />
        </div>
        <button type="submit" disabled={loading} className="btn-primary h-[48px] shrink-0 px-5">
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing
            </>
          ) : (
            <>
              Start conversation
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>

      {message ? (
        <p className="mt-2.5 flex items-start gap-2 text-[13px] text-rose-600 dark:text-rose-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {message}
        </p>
      ) : (
        <p className="mt-2.5 text-[11.5px] text-subtle">
          Works with youtube.com and youtu.be links. Captions must be available.
        </p>
      )}
    </form>
  )
}
