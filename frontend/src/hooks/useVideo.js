import { useCallback, useEffect, useRef, useState } from 'react'

import { getErrorMessage, getVideo } from '../services/api'

const POLL_INTERVAL_MS = 2500

/**
 * Loads a video record and keeps polling while it is still being indexed.
 */
export function useVideo(videoId) {
  const [video, setVideo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const timerRef = useRef(null)

  const load = useCallback(async () => {
    if (!videoId) return
    try {
      const data = await getVideo(videoId)
      setVideo(data)
      setError('')
      setNotFound(false)
      return data
    } catch (err) {
      if (err?.response?.status === 404) {
        setNotFound(true)
        setError('This video has not been processed yet.')
      } else {
        setError(getErrorMessage(err))
      }
      return null
    } finally {
      setLoading(false)
    }
  }, [videoId])

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      const data = await load()
      if (cancelled) return
      if (data?.status === 'processing') {
        timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
      }
    }

    setLoading(true)
    setVideo(null)
    setError('')
    setNotFound(false)
    poll()

    return () => {
      cancelled = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [load])

  return { video, loading, error, notFound, refresh: load }
}
