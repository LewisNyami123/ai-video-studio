import os
import re
import textwrap
import time
from datetime import datetime
from urllib.parse import quote

import requests

from app.database import SessionLocal
from app.models.video import Video, VideoStatus
from app.utils.cloudinary import upload_video, generate_thumbnail

def _import_moviepy():
    """Supports both MoviePy 1.x (classes live under moviepy.editor) and
    MoviePy 2.x (moviepy.editor was removed; classes live at the top level)."""
    for module_name in ("moviepy.editor", "moviepy"):
        try:
            module = __import__(module_name, fromlist=["ImageClip"])
            image_clip = module.ImageClip
            audio_clip = module.AudioFileClip
            concat = module.concatenate_videoclips
            composite = getattr(module, "CompositeVideoClip", None)
            return image_clip, audio_clip, composite, concat, True, module_name
        except (ImportError, AttributeError):
            continue
    return None, None, None, None, False, None


ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, MOVIEPY_AVAILABLE, _moviepy_source = _import_moviepy()
if not MOVIEPY_AVAILABLE:
    print("MoviePy import failed on both 'moviepy.editor' and 'moviepy'. Video generation will be disabled.")
elif CompositeVideoClip is None:
    print(f"CompositeVideoClip not available via {_moviepy_source}. Ken Burns effect will be disabled.")

from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

TEXT_API_URL = "https://text.pollinations.ai/{prompt}"
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/{prompt}"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"  # check console.groq.com if this ever stops working
SCENE_PADDING_SECONDS = 0.4  # brief hold on each frame after narration ends

SENTENCES_PER_SCENE = 2
MAX_SCENES = 8

SCRIPT_SYSTEM_PROMPT = (
    "You are a scriptwriter for short narrated videos on any subject at all — "
    "education, entertainment, technology, science, business, history, or culture. "
    "Write a clear, engaging spoken narration script about the given topic. "
    "Use only plain spoken sentences: no markdown, no headers, no bullet points, "
    "no emojis, no asterisks, no stage directions. "
    "Write between 120 and 220 words. "
    "End every sentence with a period so it can be split into scenes."
)


def process_video_generation(video_id: int, description: str):
    db = SessionLocal()
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        db.close()
        return

    audio_files = []
    image_files = []
    video_file = None

    try:
        # update status
        video.status = VideoStatus.PROCESSING
        video.progress = 10
        db.commit()

        # turn the topic/prompt into a full narration script
        script = generate_script(description)
        video.progress = 25
        db.commit()

        # split the script into scenes
        scenes = create_scenes(script)
        video.progress = 40
        db.commit()

        # generate an image + audio clip per scene
        for i, scene in enumerate(scenes):
            # create image (real AI image, falls back to a text card on failure)
            img_file = f"temp_image_{video_id}_{i}.png"
            generate_scene_image(scene["text"], img_file)
            image_files.append(img_file)

            # create audio (retries on transient connection drops)
            audio_file = f"temp_audio_{video_id}_{i}.mp3"
            generate_narration(scene["text"], audio_file)
            audio_files.append(audio_file)

            video.progress = 40 + (i + 1) * (50 // max(len(scenes), 1))
            db.commit()

        # combine into a single video
        video_file = combine_to_video(image_files, audio_files, video_id)
        video.progress = 90
        db.commit()

        # upload to cloudinary (retries on transient gateway errors)
        result = upload_with_retries(video_file, f"video_{video_id}")

        if result["success"]:
            video.cloudinary_url = result["url"]
            video.cloudinary_public_id = result["public_id"]
            video.thumbnail_url = generate_thumbnail(result["public_id"])
            video.duration = result["duration"]
            video.progress = 100
            video.status = VideoStatus.COMPLETED
            video.completed_at = datetime.utcnow()
            video.title = description[:50]
        else:
            video.status = VideoStatus.FAILED
            video.error_message = result["error"]

        db.commit()

    except Exception as e:
        video.status = VideoStatus.FAILED
        video.error_message = str(e)
        db.commit()
        print(f"Error occurred while generating video: {e}")

    finally:
        # clean up temp files regardless of outcome
        for f in audio_files + image_files:
            if os.path.exists(f):
                os.remove(f)
        if video_file and os.path.exists(video_file):
            os.remove(video_file)
        db.close()


def generate_script(topic: str) -> str:
    """Expands a topic or prompt into a full narration script. Tries Pollinations
    first, then Groq (if a key is configured), then falls back to narrating the
    raw topic if every provider fails — so one provider's outage or paywall
    never blocks a run."""
    script = _script_via_pollinations(topic)
    if script:
        return script

    script = _script_via_groq(topic)
    if script:
        return script

    print("All script providers unavailable, narrating the raw prompt instead.")
    return topic


def _script_via_pollinations(topic: str):
    try:
        url = TEXT_API_URL.format(prompt=quote(topic))
        params = {
            "model": "openai",
            "temperature": 0.7,
            "system": SCRIPT_SYSTEM_PROMPT,
            "referrer": "ai-video-studio",
        }
        response = requests.get(url, params=params, timeout=30)
        if not response.ok:
            print(f"Pollinations script request failed: {response.status_code} - {response.text[:300]}")
            return None
        return clean_script(response.text) or None
    except Exception as e:
        print(f"Pollinations script generation failed ({e}).")
        return None


def _script_via_groq(topic: str):
    if not GROQ_API_KEY:
        print("No GROQ_API_KEY set, skipping Groq fallback.")
        return None
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": topic},
            ],
            "temperature": 0.7,
        }
        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        if not response.ok:
            print(f"Groq script request failed: {response.status_code} - {response.text[:300]}")
            return None
        data = response.json()
        return clean_script(data["choices"][0]["message"]["content"]) or None
    except Exception as e:
        print(f"Groq script generation failed ({e}).")
        return None


def generate_narration(text: str, output_path: str, retries: int = 3, delay: float = 2.0):
    """Generates narration audio via gTTS, retrying a few times since gTTS's
    backend (an undocumented Google Translate endpoint) is known to drop
    requests on an unstable connection rather than fail cleanly."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            return
        except Exception as e:
            last_error = e
            print(f"Narration attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError(f"Narration failed after {retries} attempts: {last_error}")


def upload_with_retries(video_file, public_id, retries: int = 3, delay: float = 4.0):
    """Retries the Cloudinary upload a few times before giving up. A transient
    gateway error on the last step shouldn't throw away an otherwise
    successful render."""
    result = None
    for attempt in range(1, retries + 1):
        result = upload_video(video_file, public_id)
        if result.get("success"):
            return result
        print(f"Upload attempt {attempt}/{retries} failed: {result.get('error')}")
        if attempt < retries:
            time.sleep(delay)
    return result


def clean_script(text: str) -> str:
    """Strips stray markdown/formatting artifacts a text model might still
    include, so nothing gets read aloud literally by the TTS engine."""
    text = re.sub(r'[*_`#]+', '', text)
    text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def create_scenes(script: str, sentences_per_scene: int = SENTENCES_PER_SCENE, max_scenes: int = MAX_SCENES):
    # split into scenes of a few sentences each, capped so render time stays reasonable
    sentences = [s.strip() for s in script.split('. ') if s.strip()]

    if not sentences:
        return [
            {"text": f"Welcome to this video about {script}.", "duration": 5},
            {"text": "Let's take a closer look.", "duration": 4},
        ]

    scenes = []
    for i in range(0, len(sentences), sentences_per_scene):
        chunk = '. '.join(sentences[i:i + sentences_per_scene]).strip()
        if not chunk.endswith('.'):
            chunk += '.'
        scenes.append({
            "text": chunk,
            "duration": max(3, len(chunk) * 0.6)
        })

    if len(scenes) > max_scenes:
        keep = scenes[:max_scenes - 1]
        overflow_text = ' '.join(s["text"] for s in scenes[max_scenes - 1:])
        keep.append({"text": overflow_text, "duration": max(3, len(overflow_text) * 0.6)})
        scenes = keep

    return scenes


def generate_scene_image(prompt: str, output_path: str, width: int = 1280, height: int = 720):
    """Generates a scene image using an AI image model. Falls back to a plain
    text card if the request fails, so a network hiccup never crashes the run."""
    try:
        image_prompt = f"cinematic, detailed illustration: {prompt}"
        params = {
            "width": width,
            "height": height,
            "nologo": "true",
            "model": "flux",
            "enhance": "true",
            "referrer": "ai-video-studio",
        }
        url = POLLINATIONS_IMAGE_URL.format(prompt=quote(image_prompt))
        response = requests.get(url, params=params, timeout=45)
        if not response.ok:
            print(f"Image generation request failed: {response.status_code} - {response.text[:300]}")
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
    except Exception as e:
        print(f"Image generation failed ({e}), falling back to a text card for this scene.")
        create_text_image(prompt, output_path)


def create_text_image(text: str, output_path: str):
    """Creates a plain text card image. Used as a fallback when AI image generation fails."""
    img = Image.new('RGB', (1280, 720), color=(20, 30, 60))
    d = ImageDraw.Draw(img)

    # try to use a font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 50)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50
            )
        except Exception:
            font = ImageFont.load_default()

    wrapped = textwrap.fill(text, width=50)
    lines = wrapped.split('\n')
    y_start = (720 - len(lines) * 60) // 2

    for i, line in enumerate(lines):
        y = y_start + i * 60
        d.text((50, y), line, font=font, fill=(255, 255, 255))

    # decorative bars
    d.rectangle([50, 50, 1230, 50], fill=(100, 150, 255))
    d.rectangle([50, 620, 1230, 670], fill=(100, 150, 255))

    img.save(output_path)


def apply_ken_burns(image_clip, duration, zoom=0.06):
    """Adds a subtle continuous zoom-in (Ken Burns) effect, keeping the output
    frame size fixed. Falls back to a static frame if the effect can't be
    applied on this MoviePy version, rather than failing the whole video."""
    try:
        w, h = image_clip.size
        zoomed = image_clip.resized(lambda t: 1 + zoom * (t / duration))
        zoomed = zoomed.with_position(("center", "center"))
        return CompositeVideoClip([zoomed], size=(w, h)).with_duration(duration)
    except Exception as e:
        print(f"Ken Burns effect skipped ({e}), using a static frame instead.")
        return image_clip


def combine_to_video(image_files, audio_files, video_id):
    """Combines images and audio into a single video. Each scene's length is
    driven by its actual narration length, not a guess, so video and audio
    always stay in sync."""
    clips = []
    for img_path, audio_path in zip(image_files, audio_files):
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration + SCENE_PADDING_SECONDS

        image_clip = ImageClip(img_path, duration=duration)
        image_clip = apply_ken_burns(image_clip, duration)
        clip = image_clip.with_audio(audio_clip)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    output = f"video_output_{video_id}.mp4"
    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    return output