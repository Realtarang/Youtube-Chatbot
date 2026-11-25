import { BookOpen, History, Moon, Play, Plus, Sun } from 'lucide-react'
import { Link, NavLink } from 'react-router-dom'

import { useTheme } from '../context/ThemeContext.jsx'
import { API_BASE_URL } from '../services/api'

const linkClass = ({ isActive }) =>
  `inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition ${
    isActive
      ? 'bg-elevated text-fg'
      : 'text-muted hover:bg-elevated hover:text-fg'
  }`

export default function Navbar() {
  const { resolved, toggle } = useTheme()
  const nextTheme = resolved === 'dark' ? 'light' : 'dark'

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
            <Play className="h-3.5 w-3.5 fill-white text-white" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-fg">VideoMind</span>
          <span className="hidden rounded border border-line px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em] text-subtle sm:inline">
            Beta
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>
            <Play className="h-4 w-4 sm:hidden" />
            <span className="hidden sm:inline">Home</span>
          </NavLink>
          <NavLink to="/history" className={linkClass}>
            <History className="h-4 w-4" />
            <span className="hidden sm:inline">Library</span>
          </NavLink>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className={`${linkClass({ isActive: false })} hidden sm:inline-flex`}
          >
            <BookOpen className="h-4 w-4" />
            API
          </a>

          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${nextTheme} mode`}
            title={`Switch to ${nextTheme} mode`}
            className="ml-1 rounded-lg border border-line p-2 text-muted transition hover:bg-elevated hover:text-fg"
          >
            {resolved === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <Link
            to="/"
            className="ml-1.5 inline-flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-2 text-[13px] font-semibold text-fg transition hover:border-line-strong"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">New video</span>
          </Link>
        </nav>
      </div>
    </header>
  )
}
