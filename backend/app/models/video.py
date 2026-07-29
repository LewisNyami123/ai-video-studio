from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Float
from sqlalchemy.sql import func
from app.database import Base
import enum


class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING)
    progress = Column(Float, default=0.0)

    cloudinary_url = Column(String(500), nullable=True)
    cloudinary_public_id = Column(String(255), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    duration = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "title": self.title,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "video_url": self.cloudinary_url,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error_message,
        }