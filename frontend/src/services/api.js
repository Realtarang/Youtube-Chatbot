import axios from 'axios'

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180_000,
  headers: { 'Content-Type': 'application/json' },
})

const FALLBACK_ERROR = 'Something went wrong. Please try again.'

export function getErrorMessage(error, fallback = FALLBACK_ERROR) {
  if (error?.response?.data?.error?.message) return error.response.data.error.message
  if (error?.response?.data?.detail && typeof error.response.data.detail === 'string') {
    return error.response.data.detail
  }
  if (error?.code === 'ECONNABORTED') {
    return 'The request took too long. Long videos can take a while to index - please retry.'
  }
  if (!error?.response) {
    return `Could not reach the VideoMind API at ${API_BASE_URL}. Is the backend running?`
  }
  return fallback
}

export async function processVideo(url) {
  const { data } = await api.post('/api/video/process', { url })
  return data
}

export async function getVideo(videoId) {
  const { data } = await api.get(`/api/video/${videoId}`)
  return data
}

export async function getTranscript(videoId) {
  const { data } = await api.get(`/api/video/${videoId}/transcript`)
  return data
}

export async function searchVideo(videoId, query) {
  const { data } = await api.post(`/api/video/${videoId}/search`, { query })
  return data
}

export async function getChatHistory(videoId, sessionId) {
  const { data } = await api.get(`/api/video/${videoId}/history`, { params: { session_id: sessionId } })
  return data
}

export async function sendMessage({ videoId, question, sessionId, detail = 'balanced' }) {
  const { data } = await api.post('/api/chat', {
    video_id: videoId,
    question,
    session_id: sessionId || undefined,
    detail,
  })
  return data
}

export async function clearChat(sessionId) {
  const { data } = await api.delete(`/api/chat/${sessionId}`)
  return data
}

export async function deleteVideo(videoId) {
  const { data } = await api.delete(`/api/video/${videoId}`)
  return data
}

export async function generateSummary(videoId) {
  const { data } = await api.post(`/api/video/${videoId}/summary`)
  return data
}

export async function generateQuiz(videoId, count = 5) {
  const { data } = await api.post(`/api/video/${videoId}/quiz`, null, { params: { count } })
  return data
}

export async function generateNotes(videoId) {
  const { data } = await api.post(`/api/video/${videoId}/notes`)
  return data
}

export async function generateFlashcards(videoId, count = 8) {
  const { data } = await api.post(`/api/video/${videoId}/flashcards`, null, { params: { count } })
  return data
}

export { API_BASE_URL }
