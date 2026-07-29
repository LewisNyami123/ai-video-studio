import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = "http://localhost:8000"

type VideoState = {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  video_url?: string | null
  title?: string | null
  error?: string | null
  [key: string]:any
}

const STAGES = [
  { label: 'Script', at: 10 },
  { label: 'Scenes', at: 40 },
  { label: 'Render', at: 90 },
  { label: 'Done', at: 100 },
]

const EXAMPLE_PROMPTS = [
  'The psychology behind why habits are so hard to break',
  'A short history of the Roman aqueducts',
  'Why anime fight scenes feel so satisfying to watch',
]

function currentStageIndex(progress: number) {
  let idx = 0
  STAGES.forEach((stage, i) => {
    if (progress >= stage.at) idx = i
  })
  return idx
}

function App() {
  const [description, setDescription] = useState("")
  const [loading, setLoading] = useState(false)
  const [video, setVideo] = useState<VideoState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const intervalRef = useRef<number | null>(null)

  // stop polling if the component unmounts mid-generation
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const generateVideo = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!description.trim() || loading) return

    // cancel any poll from a previous run before starting a new one
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    setLoading(true)
    setError(null)
    setVideo(null)

    try {
      const response = await fetch(`${API_URL}/api/videos/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description })
      })

      if (!response.ok) {
        throw new Error(`server-error-${response.status}`)
      }

      const results = await response.json()
      setVideo(results)

      intervalRef.current = window.setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_URL}/api/videos/status/${results.id}`)
          if (!statusRes.ok) throw new Error(`server-error-${statusRes.status}`)
          const status = await statusRes.json()
          setVideo(status)

          if (status.status === 'completed' || status.status === 'failed') {
            if (intervalRef.current) clearInterval(intervalRef.current)
            intervalRef.current = null
            setLoading(false)
          }
        } catch {
          if (intervalRef.current) clearInterval(intervalRef.current)
          intervalRef.current = null
          setLoading(false)
          setError("Lost the connection while checking on your video. The server may be down.")
        }
      }, 2000)

    } catch {
      setLoading(false)
      setError("Couldn't reach the studio — check that the server is running and try again.")
    }
  }

  const handleDownload = async () => {
    if (!video?.video_url || downloading) return
    setDownloading(true)
    try {
      const res = await fetch(video.video_url)
      if (!res.ok) throw new Error('download-failed')
      const blob = await res.blob()
      const blobUrl = URL.createObjectURL(blob)

      const safeName = (video.title || 'ai-video')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '')

      const link = document.createElement('a')
      link.href = blobUrl
      link.download = `${safeName || 'ai-video'}.mp4`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(blobUrl)
    } catch {
      setError("Couldn't download the video directly — try opening it and using \"Save video as\" instead.")
    } finally {
      setDownloading(false)
    }
  }

  const stageIndex = video ? currentStageIndex(video.progress ?? 0) : -1

  return (
    <div className="stage">
      <div className="slate">
        <header className="masthead">
          <div className="stripe-bar" aria-hidden="true" />
          <div className="masthead-row">
            <h1>AI Video Studio</h1>
            <span className="tally-dot" aria-hidden="true" />
          </div>
          <p className="tagline">Write a scene. Watch it get shot, scored, and cut together.</p>
        </header>

        <form onSubmit={generateVideo} className="script-card">
          <label htmlFor="description" className="script-label">Scene description</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. A short history of the Roman aqueducts, told for someone who's never heard of them..."
            rows={5}
            disabled={loading}
            maxLength={800}
          />
          <div className="script-footer">
            <span className="char-count">{description.length}/800</span>
            <button type="submit" className="action-btn" disabled={loading || !description.trim()}>
              {loading ? 'Generating…' : '▶ Generate video'}
            </button>
          </div>
        </form>

        {!video && !loading && (
          <div className="examples">
            <span className="examples-label">Or start from one of these</span>
            <div className="chip-row">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  type="button"
                  key={prompt}
                  className="chip"
                  onClick={() => setDescription(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="error-frame" role="alert">
            <strong>Generation stopped.</strong> {error}
          </div>
        )}

        {video && video.status !== 'failed' && (
          <div className="filmstrip-wrap">
            <div className="filmstrip">
              {STAGES.map((stage, i) => (
                <div
                  key={stage.label}
                  className={
                    'frame' +
                    (i <= stageIndex ? ' frame-lit' : '') +
                    (i === stageIndex && video.status === 'processing' ? ' frame-active' : '')
                  }
                >
                  <span className="sprockets top" aria-hidden="true" />
                  <span className="frame-label">{stage.label}</span>
                  <span className="sprockets bottom" aria-hidden="true" />
                </div>
              ))}
            </div>
            <div className="timecode">
              <span>{video.status === 'completed' ? 'READY' : STAGES[stageIndex]?.label.toUpperCase()}</span>
              <span>{Math.round(video.progress ?? 0)}%</span>
            </div>
          </div>
        )}

        {video && video.status === 'completed' && video.video_url && (
          <div className="reel-card">
            <video src={video.video_url} controls />
            <div className="reel-footer">
              <p className="reel-caption">{video.title || description.slice(0, 60)}</p>
              <button
                type="button"
                className="download-btn"
                onClick={handleDownload}
                disabled={downloading}
              >
                {downloading ? 'Downloading…' : '⬇ Download'}
              </button>
            </div>
          </div>
        )}

        {video && video.status === 'failed' && (
          <div className="error-frame" role="alert">
            <strong>This take didn't make it.</strong>{' '}
            {video.error || 'The render failed before it finished. Try again with a shorter description.'}
          </div>
        )}
      </div>
    </div>
  )
}

export default App