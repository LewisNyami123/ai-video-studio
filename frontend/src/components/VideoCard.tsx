export type VideoSummary = {
  id: number
  title?: string | null
  description: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  video_url?: string | null
  thumbnail_url?: string | null
  created_at?: string | null
  error?: string | null
}

const STATUS_LABEL: Record<VideoSummary['status'], string> = {
  pending: 'Queued',
  processing: 'Generating',
  completed: 'Ready',
  failed: 'Failed',
}

function formatDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

type VideoCardProps = {
  video: VideoSummary
  onSelect: (video: VideoSummary) => void
}

function VideoCard({ video, onSelect }: VideoCardProps) {
  return (
    <button
      type="button"
      className={`video-card status-${video.status}`}
      onClick={() => onSelect(video)}
    >
      <div className="video-card-thumb">
        {video.thumbnail_url ? (
          <img src={video.thumbnail_url} alt="" />
        ) : (
          <span className="video-card-thumb-fallback" aria-hidden="true">▶</span>
        )}
        <span className="video-card-status">{STATUS_LABEL[video.status]}</span>
      </div>
      <div className="video-card-body">
        <p className="video-card-title">{video.title || video.description.slice(0, 60)}</p>
        <span className="video-card-date">{formatDate(video.created_at)}</span>
      </div>
    </button>
  )
}

export default VideoCard