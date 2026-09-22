# video.py
#
# Renders a narration script into a short vertical video: cloned-voice
# narration audio (Chatterbox TTS, conditioned on a reference voice
# clip) synced to simple text-slide captions, assembled with ffmpeg.
# No LLM calls happen here -- the caller supplies the finished script
# text, same as write_file takes finished content.

import io
import json
import subprocess
import textwrap
import urllib.request
from pathlib import Path

import torchaudio
from PIL import Image, ImageDraw, ImageFont

from .config import IMAGE_SERVER_URL, VOICE_REFERENCE_PATH


VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
TEXT_COLOR = (255, 255, 255)
MAX_CHARS_PER_SLIDE = 110
WRAP_WIDTH = 24
MIN_SLIDE_SECONDS = 2.0

# Controls how expressive/varied the cloned narration sounds -- higher
# exaggeration = more emotional inflection, cfg_weight trades strict
# adherence to the reference delivery against natural variation.
EXAGGERATION = 0.6
CFG_WEIGHT = 0.5

_model = None


def _load_model():
    """
    Lazily load and cache the Chatterbox model -- it's expensive to
    initialize (multi-second GPU load), so create_video calls within
    the same process reuse it instead of reloading every time.
    """
    global _model

    if _model is None:
        from chatterbox.tts import ChatterboxTTS

        _model = ChatterboxTTS.from_pretrained(device="cuda")

    return _model

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default(size=size)


def _split_long_sentence(sentence, max_chars):
    """
    Split an over-length sentence on clause boundaries (commas) rather
    than raw character width, so a chunk never gets orphaned from the
    words it depends on (e.g. "...prefer crawling over" / "swimming"
    losing "swimming"'s subject). Falls back to word-wrapping only for
    a single clause that's still too long on its own.
    """
    clauses = [clause.strip() for clause in sentence.split(",") if clause.strip()]

    chunks = []
    current = ""

    for clause in clauses:
        candidate = f"{current}, {clause}" if current else clause

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = clause

    if current:
        chunks.append(current)

    final = []

    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            final.extend(textwrap.wrap(chunk, width=max_chars))

    return final


def split_script_into_slides(script, max_chars=MAX_CHARS_PER_SLIDE):
    """
    Break narration text into short caption chunks, one per slide.
    Splits on sentence boundaries first, then splits any sentence
    longer than max_chars on clause boundaries so a single slide
    never overflows.
    """
    sentences = [
        sentence.strip()
        for sentence in script.replace("\n", " ").split(".")
        if sentence.strip()
    ]

    slides = []

    for sentence in sentences:
        if len(sentence) <= max_chars:
            slides.append(sentence)
        else:
            slides.extend(_split_long_sentence(sentence, max_chars))

    return slides or [script.strip()]


def generate_background(prompt):
    """
    Generate a slide background image from caption text, upscaled to
    the video frame size. The caption text doubles as the image prompt
    -- no LLM call, consistent with this module's rule that the caller
    supplies finished content, not a request for us to interpret.

    Generation itself runs on a separate machine (agent/image_server.py)
    rather than loading the model in this process, so it doesn't compete
    with Chatterbox for GPU memory here -- see IMAGE_SERVER_URL.
    """
    if not IMAGE_SERVER_URL:
        raise RuntimeError(
            "IMAGE_SERVER_URL is not set. Run agent/image_server.py on "
            "the machine doing image generation, then set "
            "IMAGE_SERVER_URL=http://<that machine>:8420 in .env."
        )

    request = urllib.request.Request(
        f"{IMAGE_SERVER_URL}/generate",
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        image = Image.open(io.BytesIO(response.read())).convert("RGB")

    return image.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)


def render_slide(text, output_path, size=(VIDEO_WIDTH, VIDEO_HEIGHT)):
    image = generate_background(text).convert("RGBA")

    font = _load_font(72)
    lines = textwrap.wrap(text, width=WRAP_WIDTH) or [text]
    line_spacing = 16

    measurer = ImageDraw.Draw(image)
    boxes = [measurer.textbbox((0, 0), line, font=font) for line in lines]
    heights = [box[3] - box[1] for box in boxes]
    total_height = sum(heights) + line_spacing * (len(lines) - 1)

    y = (size[1] - total_height) // 2
    scrim_padding = 32

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        [(0, y - scrim_padding), (size[0], y + total_height + scrim_padding)],
        fill=(0, 0, 0, 140),
    )
    image = Image.alpha_composite(image, overlay)

    draw = ImageDraw.Draw(image)

    for line, box, height in zip(lines, boxes, heights):
        width = box[2] - box[0]
        x = (size[0] - width) // 2
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += height + line_spacing

    image.convert("RGB").save(output_path)


def synthesize_narration(script, output_path):
    if not VOICE_REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Voice reference clip not found: {VOICE_REFERENCE_PATH}"
        )

    model = _load_model()

    wav = model.generate(
        script,
        audio_prompt_path=str(VOICE_REFERENCE_PATH),
        exaggeration=EXAGGERATION,
        cfg_weight=CFG_WEIGHT,
    )

    torchaudio.save(str(output_path), wav, model.sr)


def get_audio_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    return float(result.stdout.strip())


def assemble_video(slide_paths, durations, audio_path, output_path):
    """
    Concatenate timed slide images and mux in the narration audio.
    Uses the ffmpeg concat demuxer, which requires the final entry to
    be repeated without a duration line -- otherwise the last slide's
    duration is silently dropped.
    """
    concat_path = output_path.parent / "concat.txt"

    lines = []
    for path, duration in zip(slide_paths, durations):
        lines.append(f"file '{path.name}'")
        lines.append(f"duration {duration:.3f}")
    lines.append(f"file '{slide_paths[-1].name}'")

    concat_path.write_text("\n".join(lines), encoding="utf-8")

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-i", str(audio_path),
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},format=yuv420p",
            "-c:v", "libx264", "-r", "30",
            "-c:a", "aac", "-shortest",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=output_path.parent,
    )

    concat_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")


def create_video(script, output_dir):
    """
    Render a narration script into output_dir/video.mp4. output_dir
    must already be inside the sandbox -- the caller (tools.py) is
    responsible for path containment via safe_path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = output_dir / "narration.wav"
    synthesize_narration(script, audio_path)

    total_duration = get_audio_duration(audio_path)

    slides_text = split_script_into_slides(script)
    per_slide_seconds = max(total_duration / len(slides_text), MIN_SLIDE_SECONDS)

    slide_paths = []

    for index, text in enumerate(slides_text):
        slide_path = output_dir / f"slide_{index:03d}.png"
        render_slide(text, slide_path)
        slide_paths.append(slide_path)

    durations = [per_slide_seconds] * len(slide_paths)

    video_path = output_dir / "video.mp4"
    assemble_video(slide_paths, durations, audio_path, video_path)

    return video_path
