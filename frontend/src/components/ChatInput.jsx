import { ArrowUp, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

export default function ChatInput({
  onSend,
  disabled = false,
  loading = false,
  placeholder,
  draft = '',
  onDraftHandled,
}) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    const node = textareaRef.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`
  }, [value])

  useEffect(() => {
    if (!draft) return
    setValue(draft)
    onDraftHandled?.()
    textareaRef.current?.focus()
  }, [draft, onDraftHandled])

  const submit = () => {
    const question = value.trim()
    if (!question || disabled || loading) return
    onSend(question)
    setValue('')
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-line bg-surface p-3">
      <div className="flex items-end gap-2 rounded-lg border border-line bg-canvas p-1.5 transition focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder || 'Ask a question about this video…'}
          className="max-h-40 min-h-[36px] flex-1 resize-none bg-transparent px-2 py-1.5 text-[14px] text-fg placeholder:text-subtle focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || loading || !value.trim()}
          aria-label="Send question"
          className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </button>
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-subtle">
        Enter to send · Shift + Enter for a new line · answers come only from the transcript
      </p>
    </div>
  )
}
