from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoCreate, VideoResponse
from app.services.video_generator import process_video_generation

router = APIRouter()


@router.post("/generate", response_model=VideoResponse)
async def generate_video(
    data: VideoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # create database record
    video = Video(
        description=data.description,
        title=data.title or data.description[:50],
        status=VideoStatus.PENDING
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # start background task
    background_tasks.add_task(
        process_video_generation,
        video_id=video.id,
        description=data.description
    )
    return video.to_dict()


@router.get("/status/{video_id}")
async def get_video_status(
    video_id: int,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video.to_dict()


@router.get("/", response_model=List[VideoResponse])
async def list_videos(
    db: Session = Depends(get_db)
):
    videos = db.query(Video).order_by(desc(Video.created_at)).all()
    return [video.to_dict() for video in videos]