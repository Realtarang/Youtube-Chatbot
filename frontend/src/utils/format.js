export function formatTimestamp(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value < 0) return '00:00'
  const total = Math.floor(value)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const pad = (n) => String(n).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`
}

export function formatDuration(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value <= 0) return null
  const total = Math.round(value)
  const hours = Math.floor(total / 3600)
  const minutes = Math.round((total % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes} min`
  return `${total}s`
}

export function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function youtubeUrl(videoId, seconds = null) {
  const base = `https://www.youtube.com/watch?v=${videoId}`
  if (seconds === null || seconds === undefined) return base
  return `${base}&t=${Math.max(0, Math.floor(seconds))}s`
}

export function truncate(text, max = 280) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text
}
