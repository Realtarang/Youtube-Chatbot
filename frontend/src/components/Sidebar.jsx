import {
  AlertCircle,
  BookOpen,
  Check,
  ClipboardList,
  Copy,
  ExternalLink,
  FileText,
  GraduationCap,
  Languages,
  Layers,
  Loader2,
  RotateCcw,
  ScrollText,
  User,
} from 'lucide-react'

import FindMoments from './FindMoments.jsx'
import VideoPlayer from './VideoPlayer.jsx'
import { formatDuration, youtubeUrl } from '../utils/format'

const TOOLS = [
  { key: 'summary', label: 'Summary', icon: BookOpen, hint: 'Short + detailed summary' },
  { key: 'quiz', label: 'Quiz', icon: GraduationCap, hint: 'MCQs from the transcript' },
  { key: 'notes', label: 'Notes', icon: ScrollText, hint: 'Structured study notes' },
  { key: 'flashcards', label: 'Flashcards', icon: Layers, hint: 'Cards with spaced review' },
]

function StatusBadge({ status }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
        <Check className="h-3 w-3" />
        Indexed
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/25 bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-600 dark:text-rose-300">
        <AlertCircle className="h-3 w-3" />
        Failed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-300">
      <Loader2 className="h-3 w-3 animate-spin" />
      Processing
    </span>
  )
}

export default function Sidebar({
  video,
  playerRef,
  onOpenTranscript,
  onOpenTool,
  onCopy,
  copied,
  onRetry,
  retrying,
  onSeek,
}) {
  const ready = video.status === 'ready'
  const duration = formatDuration(video.duration_seconds)

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-line bg-black">
        <VideoPlayer ref={playerRef} videoId={video.video_id} title={video.title} />
      </div>

      <FindMoments videoId={video.video_id} onSeek={onSeek} disabled={!ready} />

      <div className="surface p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <StatusBadge status={video.status} />
          <div className="flex items-center gap-1.5 text-[11px] text-subtle">
            {video.transcript_available ? (
              <>
                <FileText className="h-3.5 w-3.5" />
                Transcript captured
              </>
            ) : (
              'No transcript'
            )}
          </div>
        </div>

        <h1 className="mt-3 text-[17px] font-semibold leading-snug tracking-tight text-fg">
          {video.title}
        </h1>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted">
          {video.channel && (
            <span className="inline-flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-subtle" />
              {video.channel}
            </span>
          )}
          {duration && <span className="tabular-nums text-subtle">{duration}</span>}
          {video.transcript_language && (
            <span className="inline-flex items-center gap-1.5">
              <Languages className="h-3.5 w-3.5 text-subtle" />
              {video.transcript_language.toUpperCase()}
            </span>
          )}
        </div>

        <div className="mt-4 grid grid-cols-3 divide-x divide-line rounded-lg border border-line bg-elevated text-center">
          {[
            { label: 'Passages', value: video.chunk_count || 0 },
            { label: 'Cues', value: video.segment_count || 0 },
            { label: 'Status', value: ready ? 'Ready' : video.status === 'failed' ? 'Failed' : 'Indexing' },
          ].map((stat) => (
            <div key={stat.label} className="px-2 py-2.5">
              <p className="text-[13px] font-semibold tabular-nums text-fg">{stat.value}</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-[0.1em] text-subtle">{stat.label}</p>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={onOpenTranscript} className="btn-ghost flex-1 min-w-[8rem]">
            <ClipboardList className="h-4 w-4" />
            Transcript
          </button>
          <button type="button" onClick={onCopy} className="btn-ghost flex-1 min-w-[7rem]">
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy link
              </>
            )}
          </button>
          <a
            href={youtubeUrl(video.video_id)}
            target="_blank"
            rel="noreferrer"
            className="btn-ghost flex-1 min-w-[7rem]"
          >
            <ExternalLink className="h-4 w-4" />
            YouTube
          </a>
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <p className="label mb-2.5">Study tools</p>
          <div className="grid grid-cols-2 gap-2">
            {TOOLS.map((tool) => (
              <button
                key={tool.key}
                type="button"
                disabled={!ready}
                onClick={() => onOpenTool(tool.key)}
                title={tool.hint}
                className="flex items-center gap-2 rounded-lg border border-line bg-elevated px-2.5 py-2.5 text-xs font-medium text-body transition hover:border-accent/40 hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
              >
                <tool.icon className="h-4 w-4 text-accent-text" />
                {tool.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {video.status === 'processing' && (
        <div className="surface p-4">
          <div className="flex items-center gap-2 text-sm text-accent-text">
            <Loader2 className="h-4 w-4 animate-spin" />
            Building the search index
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-elevated">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-accent" />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Chunking {video.segment_count} caption cues and generating embeddings. This usually
            takes a few seconds after the transcript is extracted.
          </p>
        </div>
      )}

      {video.status === 'failed' && (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/[0.06] p-4">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-rose-600 dark:text-rose-200">Processing failed</p>
              <p className="mt-1 text-xs leading-relaxed text-rose-600/80 dark:text-rose-200/70">
                {video.error_message || 'The transcript could not be indexed.'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className="btn-ghost mt-3 w-full text-xs"
          >
            {retrying ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Retrying…
              </>
            ) : (
              <>
                <RotateCcw className="h-3.5 w-3.5" />
                Reprocess video
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}
