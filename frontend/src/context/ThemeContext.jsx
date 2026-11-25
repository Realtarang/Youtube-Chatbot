import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_KEY = 'videomind.theme'
const ThemeContext = createContext(null)

function readStoredTheme() {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === 'light' || value === 'dark' || value === 'system') return value
  } catch {
    // Storage may be blocked; fall back to the app default.
  }
  return 'dark'
}

function systemPrefersDark() {
  if (typeof window === 'undefined' || !window.matchMedia) return true
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolveTheme(theme) {
  if (theme === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return theme
}

function applyTheme(resolved) {
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  root.style.colorScheme = resolved
}

/**
 * Theme is a device preference: stored locally, applied before paint by the
 * inline script in index.html and kept in sync here.
 */
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readStoredTheme)

  useEffect(() => {
    applyTheme(resolveTheme(theme))
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // The visible theme still applies for this session.
    }
  }, [theme])

  useEffect(() => {
    if (theme !== 'system' || !window.matchMedia) return undefined
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme(media.matches ? 'dark' : 'light')
    media.addEventListener('change', handler)
    return () => media.removeEventListener('change', handler)
  }, [theme])

  const value = useMemo(() => {
    const resolved = resolveTheme(theme)
    return {
      theme,
      resolved,
      setTheme,
      toggle: () => setTheme(resolved === 'dark' ? 'light' : 'dark'),
    }
  }, [theme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside a ThemeProvider')
  return context
}
