from pydantic import BaseModel
from typing import Optional


class VideoCreate(BaseModel):
    description: str
    title: Optional[str] = None


class VideoResponse(BaseModel):
    id: int
    description: str
    title: Optional[str] = None
    status: str
    progress: float
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True