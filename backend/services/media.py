import shutil
import subprocess
from pathlib import Path

# Formatos comuns de vídeo (áudio extraído com ffmpeg).
VIDEO_SUFFIXES = {
    ".mp4",
    ".webm",
    ".mkv",
    ".mov",
    ".avi",
    ".mpeg",
    ".mpg",
    ".m4v",
    ".ogv",
    ".3gp",
}


def is_video(suffix: str) -> bool:
    return suffix.lower() in VIDEO_SUFFIXES


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_audio_for_whisper(src: Path, dst_wav: Path, timeout_sec: int = 180) -> None:
    """Converte ou extrai áudio para WAV mono 16 kHz (formato ideal para o Whisper)."""
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(dst_wav),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_sec)
