import {
  ArrowRight,
  Check,
  Clock,
  FileDown,
  Layers,
  ListChecks,
  MessagesSquare,
  Search,
  ShieldCheck,
  Sparkles,
  Youtube,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import VideoInput from '../components/VideoInput.jsx'
import { useHistory } from '../context/HistoryContext.jsx'
import { API_BASE_URL, getErrorMessage, processVideo } from '../services/api'

const EXAMPLES = [
  'What are the main arguments in this talk?',
  'Summarize the key concepts for me.',
  'Where does the speaker explain the workflow?',
  'What examples are used, and at what timestamps?',
]

const FEATURES = [
  {
    icon: Clock,
    title: 'Timestamped citations',
    body: 'Every answer links to the transcript moments it came from. One click seeks the player to that exact second.',
  },
  {
    icon: Search,
    title: 'Find any moment',
    body: 'Search the video in plain language and get the passages that matter, ranked, with a jump-to timestamp.',
  },
  {
    icon: Layers,
    title: 'Answer depth you control',
    body: 'Ask for a quick answer, a normal explanation, or a deep dive — each mode retrieves a different amount of context.',
  },
  {
    icon: ListChecks,
    title: 'Summary, quiz and notes',
    body: 'Turn a long video into study material: short and detailed summaries, MCQs with explanations, structured notes.',
  },
  {
    icon: MessagesSquare,
    title: 'Flashcards that stick',
    body: 'Auto-generated cards with spaced review, so the ideas are still there a week after you watched.',
  },
  {
    icon: FileDown,
    title: 'Export and verify',
    body: 'Copy answers, download summaries, notes and quizzes as Markdown, and check every claim against its source.',
  },
]

const STEPS = [
  {
    step: '01',
    title: 'Paste a YouTube link',
    body: 'Any public youtube.com or youtu.be video with captions. Metadata and the transcript are extracted on the server.',
  },
  {
    step: '02',
    title: 'The transcript is indexed',
    body: 'Captions are cleaned, split into overlapping chunks with accurate times, embedded and stored for search.',
  },
  {
    step: '03',
    title: 'Ask, verify, jump',
    body: 'Each question retrieves the most relevant moments and the AI answers strictly from that context, with citations.',
  },
]

const TRUST = [
  { icon: ShieldCheck, text: 'No sign-up or account needed' },
  { icon: Youtube, text: 'Public videos with captions' },
  { icon: Clock, text: 'Answers cite real timestamps' },
]

export default function Home() {
  const navigate = useNavigate()
  const { addEntry } = useHistory()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (url) => {
    setLoading(true)
    setError('')
    try {
      const data = await processVideo(url)
      if (data?.video) addEntry(data.video)
      navigate(`/chat/${data.video.video_id}`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="relative mx-auto max-w-4xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
          <div className="flex justify-center">
            <span className="chip border-accent/30 text-accent-text">
              <Sparkles className="h-3.5 w-3.5" />
              Transcript-grounded answers
            </span>
          </div>

          <h1 className="mx-auto mt-6 max-w-3xl text-balance text-center text-4xl font-semibold leading-[1.1] tracking-tight text-fg sm:text-5xl">
            Ask any YouTube video <span className="text-accent-text">anything.</span>
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-center text-[15px] leading-relaxed text-muted sm:text-base">
            VideoMind reads the transcript, finds the moments that matter and answers with the
            citations to prove it. No watching at 2× speed, no guessing where in the video it was.
          </p>

          <div className="mx-auto mt-9 max-w-2xl">
            <div className="surface p-3 sm:p-4">
              <VideoInput onSubmit={handleSubmit} loading={loading} error={error} autoFocus />
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-muted">
            {TRUST.map((item) => (
              <span key={item.text} className="inline-flex items-center gap-1.5">
                <item.icon className="h-3.5 w-3.5 text-subtle" />
                {item.text}
              </span>
            ))}
          </div>

          <div className="mx-auto mt-9 max-w-2xl">
            <p className="label text-center">Ask things like</p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((example) => (
                <span key={example} className="chip">
                  {example}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Why it is trustworthy */}
      <section className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              title: 'Grounded by construction',
              body: 'Answers are generated from retrieved transcript passages only, never from the model’s general knowledge.',
            },
            {
              title: 'Verifiable in one click',
              body: 'Each reply lists the passages behind it, with the timestamp, so you can check the claim in the video itself.',
            },
            {
              title: 'Honest when unsure',
              body: 'If the video does not cover something, VideoMind says so instead of inventing an answer.',
            },
          ].map((item) => (
            <div key={item.title} className="surface p-5">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-600 dark:text-emerald-300/90">
                <Check className="h-3.5 w-3.5" />
                Trust
              </span>
              <h3 className="mt-2.5 text-sm font-semibold text-fg">{item.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto w-full max-w-6xl px-4 pb-14 sm:px-6">
        <div className="max-w-xl">
          <p className="label text-accent-text">Capabilities</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            Everything you need to actually understand the video
          </h2>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="surface p-5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-elevated text-muted">
                <feature.icon className="h-[17px] w-[17px]" />
              </span>
              <h3 className="mt-3.5 text-sm font-semibold text-fg">{feature.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6">
        <div className="surface p-6 sm:p-9">
          <div className="max-w-xl">
            <p className="label text-accent-text">How it works</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
              From link to grounded conversation
            </h2>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {STEPS.map((item) => (
              <div key={item.step} className="relative border-t border-line pt-4">
                <span className="font-mono text-[11px] font-semibold text-accent-text">
                  {item.step}
                </span>
                <h3 className="mt-1.5 text-[15px] font-semibold text-fg">{item.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{item.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-9 flex flex-col items-start gap-3 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted">
              Already processed something? Pick up where you left off.
            </p>
            <Link
              to="/history"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-accent-text transition hover:opacity-80"
            >
              Open your library
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-9 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent">
                <Sparkles className="h-3.5 w-3.5 text-white" />
              </span>
              <span className="text-sm font-semibold text-fg">VideoMind</span>
            </div>
            <p className="mt-2 max-w-md text-xs leading-relaxed text-subtle">
              Retrieval-augmented chat over YouTube transcripts. Built with FastAPI, Sentence
              Transformers, Neon PostgreSQL (pgvector) and Groq.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-subtle">
            <Link to="/" className="transition hover:text-fg">
              Home
            </Link>
            <Link to="/history" className="transition hover:text-fg">
              Library
            </Link>
            <a
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noreferrer"
              className="transition hover:text-fg"
            >
              API docs
            </a>
            <span>© {new Date().getFullYear()} VideoMind</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
