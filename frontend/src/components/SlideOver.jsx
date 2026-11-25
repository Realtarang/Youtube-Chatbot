import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function SlideOver({ open, onClose, title, subtitle, icon: Icon, children }) {
  useEffect(() => {
    if (!open) return undefined
    const handleKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  return (
    <div className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`} aria-hidden={!open}>
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ${
          open ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            {Icon && (
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-elevated text-accent-text">
                <Icon className="h-4 w-4" />
              </span>
            )}
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-fg">{title}</h2>
              {subtitle && <p className="truncate text-[11.5px] text-subtle">{subtitle}</p>}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="rounded-md p-1.5 text-muted transition hover:bg-elevated hover:text-fg"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  )
}
