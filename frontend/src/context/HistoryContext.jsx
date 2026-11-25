import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_KEY = 'videomind.history.v1'
const HistoryContext = createContext(null)

function readStoredItems() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((item) => item?.video_id) : []
  } catch {
    return []
  }
}

/**
 * History is stored per device in localStorage: no user identification is
 * configured, so another person's history is never exposed by the API.
 * Video transcripts themselves are cached server-side by video ID.
 */
export function HistoryProvider({ children }) {
  const [items, setItems] = useState(readStoredItems)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      // Storage may be full or disabled; history then only lives in memory.
    }
  }, [items])

  const addEntry = useCallback((video) => {
    if (!video?.video_id) return
    setItems((previous) => {
      const entry = {
        video_id: video.video_id,
        title: video.title || 'Untitled video',
        channel: video.channel || '',
        thumbnail_url: video.thumbnail_url || '',
        duration_seconds: video.duration_seconds || null,
        processed_at: video.processed_at || new Date().toISOString(),
        last_opened_at: new Date().toISOString(),
      }
      return [entry, ...previous.filter((item) => item.video_id !== video.video_id)].slice(0, 60)
    })
  }, [])

  const removeEntry = useCallback((videoId) => {
    setItems((previous) => previous.filter((item) => item.video_id !== videoId))
  }, [])

  const clearHistory = useCallback(() => setItems([]), [])

  const value = useMemo(
    () => ({ items, addEntry, removeEntry, clearHistory }),
    [items, addEntry, removeEntry, clearHistory],
  )

  return <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>
}

export function useHistory() {
  const context = useContext(HistoryContext)
  if (!context) throw new Error('useHistory must be used inside a HistoryProvider')
  return context
}
