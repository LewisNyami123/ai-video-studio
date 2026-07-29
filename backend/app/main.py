from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.api import videos

# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Video Studio API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# routes
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])


@app.get("/")
async def root():
    return {"status": "Online", "message": "AI Video Studio API"}


@app.get("/api/health")
async def health_check():
    return {"status": "Healthy"}