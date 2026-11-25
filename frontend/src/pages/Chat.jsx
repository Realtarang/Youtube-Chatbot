import { AlertCircle, ArrowLeft, Loader2, RotateCcw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import ChatWindow from '../components/ChatWindow.jsx'
import Sidebar from '../components/Sidebar.jsx'
import ToolsPanel from '../components/ToolsPanel.jsx'
import TranscriptViewer from '../components/TranscriptViewer.jsx'
import { useHistory } from '../context/HistoryContext.jsx'
import { useChat } from '../hooks/useChat.js'
import { useVideo } from '../hooks/useVideo.js'
import { getErrorMessage, getTranscript, processVideo } from '../services/api'
import { formatTimestamp, youtubeUrl } from '../utils/format'

export default function Chat() {
  const { videoId } = useParams()
  const { video, loading, error, notFound, refresh } = useVideo(videoId)
  const ready = video?.status === 'ready'
  const chat = useChat(videoId, ready)
  const { addEntry } = useHistory()

  const playerRef = useRef(null)
  const copyTimer = useRef(null)

  const [copied, setCopied] = useState(false)
  const [activeSeconds, setActiveSeconds] = useState(null)
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const [transcript, setTranscript] = useState(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [transcriptError, setTranscriptError] = useState('')
  const [tool, setTool] = useState(null)
  const [retrying, setRetrying] = useState(false)
  const [actionError, setActionError] = useState('')
  const [draft, setDraft] = useState('')
  const [detail, setDetail] = useState('balanced')

  useEffect(() => () => {
    if (copyTimer.current) clearTimeout(copyTimer.current)
  }, [])

  useEffect(() => {
    setTranscript(null)
    setTranscriptOpen(false)
    setTool(null)
    setActiveSeconds(null)
    setActionError('')
    setDraft('')
    setDetail('balanced')
  }, [videoId])

  useEffect(() => {
    if (video?.status === 'ready') addEntry(video)
    // Only re-register when the video becomes ready or changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.status, video?.video_id, addEntry])

  const handleSeek = useCallback((seconds) => {
    const target = Number(seconds) || 0
    playerRef.current?.seekTo(target)
    setActiveSeconds(target)
    playerRef.current?.getIframe()?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [])

  const loadTranscript = useCallback(async () => {
    setTranscriptLoading(true)
    setTranscriptError('')
    try {
      const data = await getTranscript(videoId)
      setTranscript(data)
    } catch (err) {
      setTranscriptError(getErrorMessage(err))
    } finally {
      setTranscriptLoading(false)
    }
  }, [videoId])

  const openTranscript = () => {
    setTranscriptOpen(true)
    if (!transcript && !transcriptLoading) loadTranscript()
  }

  const handleAskAboutMoment = useCallback(
    (segment) => {
      const snippet = String(segment?.text || '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 180)
      const stamp = formatTimestamp(segment?.start ?? 0)
      setDraft(
        snippet
          ? `Explain this part of the video around [${stamp}]: "${snippet}"`
          : `Explain what happens around [${stamp}] in this video.`,
      )
      setTranscriptOpen(false)
      if (segment) handleSeek(segment.start)
    },
    [handleSeek],
  )

  const handleDraftHandled = useCallback(() => setDraft(''), [])

  const handleSend = useCallback(
    (question) => chat.sendQuestion(question, detail),
    [chat, detail],
  )

  const handleCopy = async () => {
    const link = video?.url || youtubeUrl(videoId)
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1800)
    } catch {
      setActionError('Could not access the clipboard. Copy the URL from the address bar instead.')
    }
  }

  const handleRetry = async () => {
    if (!video?.url) return
    setRetrying(true)
    setActionError('')
    try {
      await processVideo(video.url)
      await refresh()
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setRetrying(false)
    }
  }

  if (loading && !video) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <p className="text-sm text-muted">Loading video…</p>
      </div>
    )
  }

  if (!video) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center px-4 py-24 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-rose-500/25 bg-rose-500/10 text-rose-500">
          <AlertCircle className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-lg font-semibold text-fg">
          {notFound ? 'Video not found' : 'Could not load the video'}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          {error || 'This video has not been processed yet. Start from the home page with its URL.'}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to="/" className="btn-primary">
            <ArrowLeft className="h-4 w-4" />
            Process a video
          </Link>
          <button type="button" onClick={refresh} className="btn-ghost">
            <RotateCcw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    )
  }

  const askedQuestions = new Set(
    chat.messages
      .filter((message) => message.role === 'user')
      .map((message) => message.content.trim().toLowerCase()),
  )
  const followups = (chat.followups.length ? chat.followups : video.suggested_questions || [])
    .filter((question) => !askedQuestions.has(String(question).trim().toLowerCase()))
    .slice(0, 3)

  return (
    <main className="mx-auto w-full max-w-[1600px] px-3 py-4 sm:px-4 lg:h-[calc(100vh-4rem)] lg:overflow-hidden lg:px-6">
      {actionError && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      <div className="grid gap-4 lg:h-full lg:grid-cols-[minmax(0,0.86fr)_minmax(0,1.14fr)]">
        <div className="min-h-0 lg:overflow-y-auto lg:pr-1">
          <Sidebar
            video={video}
            playerRef={playerRef}
            onOpenTranscript={openTranscript}
            onOpenTool={setTool}
            onCopy={handleCopy}
            copied={copied}
            onRetry={handleRetry}
            retrying={retrying}
            onSeek={handleSeek}
          />
        </div>

        <div className="h-[68vh] min-h-[26rem] lg:h-full">
          <ChatWindow
            video={video}
            messages={chat.messages}
            isLoading={chat.isLoading}
            isRestoring={chat.isRestoring}
            error={chat.error}
            onSend={handleSend}
            onClear={chat.clearConversation}
            onSeek={handleSeek}
            ready={ready}
            followups={followups}
            draft={draft}
            onDraftHandled={handleDraftHandled}
            detail={detail}
            onDetailChange={setDetail}
          />
        </div>
      </div>

      <TranscriptViewer
        open={transcriptOpen}
        onClose={() => setTranscriptOpen(false)}
        transcript={transcript}
        loading={transcriptLoading}
        error={transcriptError}
        onSeek={handleSeek}
        onAskAboutMoment={handleAskAboutMoment}
        activeSeconds={activeSeconds}
      />

      <ToolsPanel
        videoId={videoId}
        tool={tool}
        onClose={() => setTool(null)}
        onSeek={handleSeek}
      />
    </main>
  )
}
