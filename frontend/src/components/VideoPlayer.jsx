import { forwardRef, useCallback, useImperativeHandle, useRef } from 'react'

/**
 * Embedded YouTube player driven through the iframe postMessage API, so a
 * timestamp click seeks the same player instead of opening a new tab.
 */
const VideoPlayer = forwardRef(function VideoPlayer({ videoId, title }, ref) {
  const iframeRef = useRef(null)

  const sendCommand = useCallback((func, args = []) => {
    const frame = iframeRef.current
    if (!frame?.contentWindow) return
    frame.contentWindow.postMessage(
      JSON.stringify({ event: 'command', func, args }),
      'https://www.youtube.com',
    )
  }, [])

  useImperativeHandle(
    ref,
    () => ({
      seekTo(seconds) {
        const target = Math.max(0, Math.floor(Number(seconds) || 0))
        sendCommand('seekTo', [target, true])
        sendCommand('playVideo')
      },
      getIframe() {
        return iframeRef.current
      },
    }),
    [sendCommand],
  )

  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const src = `https://www.youtube-nocookie.com/embed/${videoId}?enablejsapi=1&rel=0&modestbranding=1&playsinline=1&origin=${encodeURIComponent(
    origin,
  )}`

  return (
    <div className="relative aspect-video w-full overflow-hidden bg-black">
      <iframe
        ref={iframeRef}
        src={src}
        title={title || 'YouTube video player'}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
        className="absolute inset-0 h-full w-full"
      />
    </div>
  )
})

export default VideoPlayer
