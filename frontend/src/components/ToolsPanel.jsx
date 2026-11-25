import {
  AlertCircle,
  BookOpen,
  Check,
  Copy,
  Download,
  GraduationCap,
  Layers,
  Loader2,
  RotateCcw,
  ScrollText,
  Sparkles,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import SlideOver from './SlideOver.jsx'
import TimestampLink from './TimestampLink.jsx'
import {
  generateFlashcards,
  generateNotes,
  generateQuiz,
  generateSummary,
  getErrorMessage,
} from '../services/api'

const META = {
  summary: { title: 'Video summary', subtitle: 'Generated from the transcript', icon: BookOpen },
  quiz: { title: 'Quiz', subtitle: 'Multiple choice, transcript-grounded', icon: GraduationCap },
  notes: { title: 'Structured notes', subtitle: 'Concepts, definitions and timestamps', icon: ScrollText },
  flashcards: { title: 'Flashcards', subtitle: 'Spaced review, from the transcript', icon: Layers },
}

const REQUEST = {
  summary: generateSummary,
  quiz: generateQuiz,
  notes: generateNotes,
  flashcards: generateFlashcards,
}

function buildMarkdown(tool, data) {
  const lines = []
  const withStamp = (item) => (item.timestamp ? ` (${item.timestamp})` : '')

  if (tool === 'summary') {
    lines.push('# Video summary', '')
    if (data.short_summary) lines.push(`> ${data.short_summary}`, '')
    if (data.detailed_summary) lines.push('## Detailed summary', data.detailed_summary, '')
    if (data.topics?.length) {
      lines.push('## Topics')
      data.topics.forEach((topic) => {
        lines.push(`- **${topic.title}**${withStamp(topic)}${topic.summary ? ` — ${topic.summary}` : ''}`)
      })
      lines.push('')
    }
    if (data.key_takeaways?.length) {
      lines.push('## Key takeaways')
      data.key_takeaways.forEach((item) => lines.push(`- ${item}`))
    }
  }

  if (tool === 'quiz') {
    lines.push('# Quiz', '')
    data.questions.forEach((question, index) => {
      lines.push(`**${index + 1}. ${question.question}**${withStamp(question)}`, '')
      question.options.forEach((option, optionIndex) => {
        const marker = optionIndex === question.correct_index ? 'x' : ' '
        lines.push(`- [${marker}] ${String.fromCharCode(65 + optionIndex)}. ${option}`)
      })
      if (question.explanation) lines.push('', `_Why:_ ${question.explanation}`)
      lines.push('')
    })
  }

  if (tool === 'notes') {
    lines.push(`# ${data.title || 'Video notes'}`, '')
    data.sections?.forEach((section) => {
      lines.push(`## ${section.heading}${withStamp(section)}`)
      section.points.forEach((point) => lines.push(`- ${point}`))
      lines.push('')
    })
    if (data.definitions?.length) {
      lines.push('## Definitions')
      data.definitions.forEach((definition) => {
        lines.push(`- **${definition.term}**${withStamp(definition)}: ${definition.meaning}`)
      })
      lines.push('')
    }
    if (data.key_takeaways?.length) {
      lines.push('## Key takeaways')
      data.key_takeaways.forEach((item) => lines.push(`- ${item}`))
    }
  }

  if (tool === 'flashcards') {
    lines.push('# Flashcards', '')
    data.cards?.forEach((card, index) => {
      lines.push(`**${index + 1}. ${card.front}**${withStamp(card)}`, '')
      lines.push(card.back, '')
    })
  }

  return `${lines.join('\n').trim()}\n`
}

function Paragraphs({ text }) {
  if (!text) return null
  return (
    <div className="space-y-2.5">
      {text
        .split(/\n{2,}/)
        .filter(Boolean)
        .map((paragraph, index) => (
          <p key={index} className="text-sm leading-relaxed text-body">
            {paragraph}
          </p>
        ))}
    </div>
  )
}

function SummaryView({ data, onSeek }) {
  return (
    <div className="space-y-5 p-4 sm:p-5">
      {data.short_summary && (
        <div className="rounded-lg border border-accent/25 bg-accent-soft p-4">
          <p className="label mb-1.5 text-accent-text">In short</p>
          <p className="text-sm leading-relaxed text-fg">{data.short_summary}</p>
        </div>
      )}

      {data.detailed_summary && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-fg">Detailed summary</h3>
          <Paragraphs text={data.detailed_summary} />
        </section>
      )}

      {data.topics?.length > 0 && (
        <section>
          <h3 className="mb-2.5 text-sm font-semibold text-fg">Important topics</h3>
          <ol className="space-y-2.5">
            {data.topics.map((topic, index) => (
              <li key={`${topic.title}-${index}`} className="surface-flat p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded border border-line bg-surface text-[11px] font-semibold tabular-nums text-muted">
                    {index + 1}
                  </span>
                  <p className="text-sm font-medium text-fg">{topic.title}</p>
                  {topic.timestamp_seconds !== null && topic.timestamp_seconds !== undefined && (
                    <TimestampLink seconds={topic.timestamp_seconds} onSeek={onSeek} className="ml-auto" />
                  )}
                </div>
                {topic.summary && (
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{topic.summary}</p>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {data.key_takeaways?.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-fg">Key takeaways</h3>
          <ul className="space-y-2">
            {data.key_takeaways.map((item, index) => (
              <li key={index} className="flex gap-2 text-sm leading-relaxed text-body">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function QuizView({ data, onSeek }) {
  const [selected, setSelected] = useState({})

  useEffect(() => {
    setSelected({})
  }, [data])

  const answered = Object.keys(selected).length
  const correct = data.questions.reduce(
    (total, question, index) => (selected[index] === question.correct_index ? total + 1 : total),
    0,
  )

  return (
    <div className="space-y-4 p-4 sm:p-5">
      <div className="flex items-center justify-between rounded-lg border border-line bg-elevated px-3.5 py-2.5 text-xs text-muted">
        <span>
          {answered} of {data.questions.length} answered
        </span>
        <span className="font-medium tabular-nums text-fg">{correct} correct</span>
      </div>

      {data.questions.map((question, questionIndex) => {
        const choice = selected[questionIndex]
        const isAnswered = choice !== undefined
        return (
          <div key={questionIndex} className="surface-flat p-3.5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-medium leading-relaxed text-fg">
                {questionIndex + 1}. {question.question}
              </p>
              {question.timestamp_seconds !== null && question.timestamp_seconds !== undefined && (
                <TimestampLink seconds={question.timestamp_seconds} onSeek={onSeek} />
              )}
            </div>

            <div className="mt-3 space-y-2">
              {question.options.map((option, optionIndex) => {
                const isCorrect = optionIndex === question.correct_index
                const isChosen = choice === optionIndex
                const showCorrect = isAnswered && isCorrect
                const showWrong = isAnswered && isChosen && !isCorrect
                return (
                  <button
                    key={optionIndex}
                    type="button"
                    disabled={isAnswered}
                    onClick={() =>
                      setSelected((previous) => ({ ...previous, [questionIndex]: optionIndex }))
                    }
                    className={`flex w-full items-start gap-2.5 rounded-lg border px-3 py-2 text-left text-[13px] leading-relaxed transition ${
                      showCorrect
                        ? 'border-emerald-500/45 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200'
                        : showWrong
                          ? 'border-rose-500/45 bg-rose-500/10 text-rose-600 dark:text-rose-200'
                          : 'border-line bg-surface text-body hover:border-accent/40 disabled:hover:border-line'
                    }`}
                  >
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-current text-[9px] font-semibold uppercase">
                      {String.fromCharCode(65 + optionIndex)}
                    </span>
                    <span>{option}</span>
                    {showCorrect && <Check className="ml-auto mt-0.5 h-3.5 w-3.5 shrink-0" />}
                    {showWrong && <X className="ml-auto mt-0.5 h-3.5 w-3.5 shrink-0" />}
                  </button>
                )
              })}
            </div>

            {isAnswered && (
              <div className="mt-3 rounded-lg border border-line bg-surface px-3 py-2 text-[12.5px] leading-relaxed text-muted">
                <span className="font-semibold text-fg">Why: </span>
                {question.explanation || 'See the cited moment in the transcript.'}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function NotesView({ data, onSeek }) {
  return (
    <div className="space-y-5 p-4 sm:p-5">
      <h2 className="text-base font-semibold text-fg">{data.title}</h2>

      {data.sections.map((section, index) => (
        <section key={index} className="surface-flat p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-fg">{section.heading}</h3>
            {section.timestamp_seconds !== null && section.timestamp_seconds !== undefined && (
              <TimestampLink seconds={section.timestamp_seconds} onSeek={onSeek} className="ml-auto" />
            )}
          </div>
          <ul className="mt-2 space-y-1.5">
            {section.points.map((point, pointIndex) => (
              <li key={pointIndex} className="flex gap-2 text-[13px] leading-relaxed text-muted">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {data.definitions?.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-fg">Definitions</h3>
          <dl className="space-y-2.5">
            {data.definitions.map((definition, index) => (
              <div key={index} className="surface-flat p-3">
                <dt className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                  {definition.term}
                  {definition.timestamp_seconds !== null &&
                    definition.timestamp_seconds !== undefined && (
                      <TimestampLink
                        seconds={definition.timestamp_seconds}
                        onSeek={onSeek}
                        className="ml-auto"
                      />
                    )}
                </dt>
                <dd className="mt-1 text-[13px] leading-relaxed text-muted">{definition.meaning}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {data.key_takeaways?.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-fg">Key takeaways</h3>
          <ul className="space-y-2">
            {data.key_takeaways.map((item, index) => (
              <li key={index} className="flex gap-2 text-sm leading-relaxed text-body">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

const knownKey = (videoId) => `videomind.flashcards.${videoId}`

function readKnown(videoId) {
  try {
    const raw = localStorage.getItem(knownKey(videoId))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

function writeKnown(videoId, value) {
  try {
    localStorage.setItem(knownKey(videoId), JSON.stringify(value))
  } catch {
    // Storage can be blocked; review still works for this session.
  }
}

function FlashcardsView({ data, onSeek, videoId }) {
  const cards = data.cards || []
  const [known, setKnown] = useState(() => readKnown(videoId))
  const [queue, setQueue] = useState(() => cards.map((_, index) => index))
  const [flipped, setFlipped] = useState(false)

  const card = queue.length ? cards[queue[0]] : null
  const reviewed = cards.length - queue.length

  const gotIt = () => {
    if (!card) return
    const next = [...new Set([...known, card.front])]
    setKnown(next)
    writeKnown(videoId, next)
    setQueue((previous) => previous.slice(1))
    setFlipped(false)
  }

  const reviewAgain = () => {
    setQueue((previous) => (previous.length > 1 ? [...previous.slice(1), previous[0]] : previous))
    setFlipped(false)
  }

  const restart = () => {
    setKnown([])
    writeKnown(videoId, [])
    setQueue(cards.map((_, index) => index))
    setFlipped(false)
  }

  return (
    <div className="space-y-4 p-4 sm:p-5">
      <div>
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            {reviewed} of {cards.length} marked known
          </span>
          <span className="tabular-nums">{cards.length ? Math.round((reviewed / cards.length) * 100) : 0}%</span>
        </div>
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-elevated">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${cards.length ? (reviewed / cards.length) * 100 : 0}%` }}
          />
        </div>
      </div>

      {!card ? (
        <div className="surface-flat flex flex-col items-center gap-2 px-5 py-12 text-center">
          <Check className="h-7 w-7 text-emerald-500" />
          <p className="text-sm font-semibold text-fg">Every card reviewed</p>
          <p className="max-w-xs text-xs leading-relaxed text-muted">
            Come back later and run the deck again — review at intervals is what makes it stick.
          </p>
          <button type="button" onClick={restart} className="btn-ghost mt-2 text-xs">
            <RotateCcw className="h-3.5 w-3.5" />
            Review all again
          </button>
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={() => setFlipped((previous) => !previous)}
            className="surface-flat block w-full min-h-[11rem] p-5 text-left transition hover:border-accent/40"
          >
            <span className="label text-[10px]">{flipped ? 'Answer' : 'Question'}</span>
            <p className="mt-2 text-[15px] font-medium leading-relaxed text-fg">
              {flipped ? card.back : card.front}
            </p>
            {flipped && card.timestamp_seconds !== null && card.timestamp_seconds !== undefined && (
              <TimestampLink
                seconds={card.timestamp_seconds}
                onSeek={onSeek}
                className="mt-3"
                hint="Jump to where this is covered"
              />
            )}
            {!flipped && <p className="mt-3 text-[11px] text-subtle">Click the card to reveal the answer</p>}
          </button>

          <div className="flex gap-2">
            <button type="button" onClick={reviewAgain} className="btn-ghost flex-1 text-xs">
              <RotateCcw className="h-3.5 w-3.5" />
              Needs review
            </button>
            <button
              type="button"
              onClick={flipped ? gotIt : () => setFlipped(true)}
              className="btn-primary flex-1 text-xs"
            >
              <Check className="h-3.5 w-3.5" />
              {flipped ? 'Got it' : 'Show answer'}
            </button>
          </div>

          <p className="text-center text-[11px] text-subtle">
            {queue.length} card{queue.length === 1 ? '' : 's'} left in this round ·
            progress saved on this device
          </p>
        </>
      )}
    </div>
  )
}

export default function ToolsPanel({ videoId, tool, onClose, onSeek }) {
  const [cache, setCache] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const copyTimer = useRef(null)

  useEffect(() => {
    setCache({})
    setError('')
  }, [videoId])

  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current)
    },
    [],
  )

  useEffect(() => {
    if (!tool) return undefined
    if (cache[tool]) {
      setLoading(false)
      setError('')
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')

    REQUEST[tool](videoId)
      .then((result) => {
        if (!cancelled) setCache((previous) => ({ ...previous, [tool]: result }))
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tool, videoId, cache])

  const meta = tool ? META[tool] : META.summary
  const data = tool ? cache[tool] : null

  const handleCopy = async () => {
    if (!data) return
    try {
      await navigator.clipboard.writeText(buildMarkdown(tool, data))
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1800)
    } catch {
      setError('Could not access the clipboard. Your browser blocked the copy.')
    }
  }

  const handleDownload = () => {
    if (!data) return
    const blob = new Blob([buildMarkdown(tool, data)], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `videomind-${tool}-${videoId}.md`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <SlideOver
      open={Boolean(tool)}
      onClose={onClose}
      title={meta.title}
      subtitle={meta.subtitle}
      icon={meta.icon}
    >
      {data && !loading && !error && (
        <div className="flex items-center justify-between gap-2 border-b border-line bg-surface px-4 py-2">
          <p className="text-[11px] text-subtle">Generated from this video's transcript</p>
          <div className="flex gap-1.5">
            <button type="button" onClick={handleCopy} className="btn-ghost px-2 py-1 text-[11.5px]">
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </>
              )}
            </button>
            <button type="button" onClick={handleDownload} className="btn-ghost px-2 py-1 text-[11.5px]">
              <Download className="h-3.5 w-3.5" />
              .md
            </button>
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-accent" />
            <p className="text-sm font-medium text-fg">Reading the transcript…</p>
            <p className="max-w-xs text-xs leading-relaxed text-muted">
              This is generated from the video's content. Long videos take a little longer.
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="m-4 rounded-lg border border-rose-500/25 bg-rose-500/[0.08] p-4">
            <div className="flex items-start gap-2 text-sm text-rose-600 dark:text-rose-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setError('')
                setCache((previous) => {
                  const next = { ...previous }
                  delete next[tool]
                  return next
                })
              }}
              className="btn-ghost mt-3 w-full text-xs"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Try again
            </button>
          </div>
        )}

        {!loading && !error && data && tool === 'summary' && (
          <SummaryView data={data} onSeek={onSeek} />
        )}
        {!loading && !error && data && tool === 'quiz' && <QuizView data={data} onSeek={onSeek} />}
        {!loading && !error && data && tool === 'notes' && <NotesView data={data} onSeek={onSeek} />}
        {!loading && !error && data && tool === 'flashcards' && (
          <FlashcardsView data={data} onSeek={onSeek} videoId={videoId} />
        )}
      </div>
    </SlideOver>
  )
}
