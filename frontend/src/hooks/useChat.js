import { useCallback, useEffect, useState } from 'react'

import { clearChat, getChatHistory, getErrorMessage, sendMessage } from '../services/api'

const sessionKey = (videoId) => `videomind.session.${videoId}`

function readSession(videoId) {
  try {
    return localStorage.getItem(sessionKey(videoId))
  } catch {
    return null
  }
}

/**
 * Chat state for one video: restores the stored session, sends grounded
 * questions and keeps the optimistic user bubble in sync with the server.
 */
export function useChat(videoId, enabled = true) {
  const [sessionId, setSessionId] = useState(() => (videoId ? readSession(videoId) : null))
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isRestoring, setIsRestoring] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const stored = videoId ? readSession(videoId) : null

    setSessionId(stored)
    setMessages([])
    setError('')

    if (!stored || !enabled) return undefined

    setIsRestoring(true)
    getChatHistory(videoId, stored)
      .then((data) => {
        if (cancelled) return
        if (!data?.session_id || !Array.isArray(data.messages)) {
          localStorage.removeItem(sessionKey(videoId))
          setSessionId(null)
          return
        }
        setMessages(
          data.messages.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            sources: message.sources || [],
            followups: [],
            degraded: false,
          })),
        )
      })
      .catch(() => {
        // A failed history restore must not block asking new questions.
        if (!cancelled) setMessages([])
      })
      .finally(() => {
        if (!cancelled) setIsRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [videoId, enabled])

  const sendQuestion = useCallback(
    async (raw, detail = 'balanced') => {
      const question = (raw || '').trim()
      if (!question || isLoading || !enabled) return

      setError('')
      const localId = `local-${Date.now()}`
      setMessages((previous) => [
        ...previous,
        { id: localId, role: 'user', content: question, sources: [], detail },
      ])
      setIsLoading(true)

      try {
        const data = await sendMessage({ videoId, question, sessionId, detail })
        if (data.session_id) {
          setSessionId(data.session_id)
          try {
            localStorage.setItem(sessionKey(videoId), data.session_id)
          } catch {
            // Private mode: the conversation still works for this page view.
          }
        }
        setMessages((previous) => [
          ...previous,
          {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: data.answer,
            sources: data.sources || [],
            followups: data.followups || [],
            degraded: Boolean(data.degraded),
          },
        ])
      } catch (err) {
        setError(getErrorMessage(err))
      } finally {
        setIsLoading(false)
      }
    },
    [videoId, sessionId, isLoading, enabled],
  )

  const clearConversation = useCallback(async () => {
    setError('')
    if (sessionId) {
      try {
        await clearChat(sessionId)
      } catch {
        // Even if the server call fails, clear the visible conversation.
      }
    }
    setMessages([])
  }, [sessionId])

  const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')

  return {
    messages,
    sendQuestion,
    clearConversation,
    isLoading,
    isRestoring,
    error,
    setError,
    sessionId,
    followups: lastAssistant?.followups || [],
  }
}
