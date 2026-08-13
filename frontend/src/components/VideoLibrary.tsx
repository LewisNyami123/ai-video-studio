import { useEffect, useState } from 'react'
import VideoCard, { type VideoSummary } from './VideoCard'
import { API_URL } from '../config'

type VideoLibraryProps = {
  onSelect: (video: VideoSummary) => void
}

function VideoLibrary({ onSelect }: VideoLibraryProps) {
  const [videos, setVideos] = useState<VideoSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadVideos = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_URL}/api/videos`)
        if (!res.ok) throw new Error(`server-error-${res.status}`)
        const data = await res.json()
        if (!cancelled) setVideos(data)
      } catch {
        if (!cancelled) {
          setError("Couldn't load your videos — check that the server is running.")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadVideos()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <p className="library-status">Loading your videos…</p>
  }

  if (error) {
    return (
      <div className="error-frame" role="alert">
        <strong>Couldn't load library.</strong> {error}
      </div>
    )
  }

  if (videos.length === 0) {
    return <p className="library-status">Nothing here yet — generate your first video to see it here.</p>
  }

  return (
    <div className="video-grid">
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} onSelect={onSelect} />
      ))}
    </div>
  )
}

export default VideoLibrary