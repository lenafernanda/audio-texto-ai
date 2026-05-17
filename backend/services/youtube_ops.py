"""Download e metadados do YouTube via yt-dlp, com cookies e mensagens amigáveis."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError, match_filter_func

from services.cookies_netscape import write_youtube_cookies
from services.media import extract_audio_for_whisper, ffmpeg_available

YOUTUBE_MAX_DURATION_SEC = int(os.getenv("YOUTUBE_MAX_DURATION_SEC", "900"))
YOUTUBE_MAX_DOWNLOAD_BYTES = int(os.getenv("YOUTUBE_MAX_DOWNLOAD_BYTES", str(600 * 1024 * 1024)))


def yt_dlp_available() -> bool:
    """Pacote `yt-dlp` instalado (importável)."""
    return True


def is_allowed_media_url(raw: str) -> bool:
    """Aceita URLs http(s) públicas; o yt-dlp valida o suporte ao site."""
    from urllib.parse import urlparse

    u = raw.strip()
    if not u:
        return False
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        parsed = urlparse(u)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower()
    return bool(host) and "." in host


def is_allowed_youtube_url(raw: str) -> bool:
    from urllib.parse import urlparse

    u = raw.strip()
    if not u:
        return False
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        parsed = urlparse(u)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower().split(":")[0]
    if host in ("youtu.be", "www.youtu.be"):
        return True
    if host.endswith("youtube.com"):
        return True
    if host.endswith("youtube-nocookie.com"):
        return True
    return False


def map_youtube_error(message: str) -> str:
    msg = message.lower()
    rules: list[tuple[str, str]] = [
        ("private video", "Este vídeo é privado ou não está disponível."),
        ("premieres in", "Este vídeo ainda não foi publicado (estreia futura)."),
        ("live event will begin", "Esta transmissão ao vivo ainda não começou."),
        ("members-only", "Conteúdo exclusivo para membros do canal."),
        ("join this channel", "Disponível apenas para membros do canal."),
        ("available to this channel", "Disponível apenas para assinantes ou membros."),
        (
            "sign in to confirm",
            "Este vídeo exige confirmação do YouTube. Você ainda pode baixar o arquivo manualmente e enviar aqui para transcrição.",
        ),
        ("login required", "É preciso estar autenticado no YouTube para acessar este conteúdo."),
        ("confirm your age", "Vídeo com restrição de idade no YouTube."),
        ("age-restricted", "Vídeo com restrição de idade no YouTube."),
        ("video unavailable", "Vídeo indisponível ou removido."),
        ("copyright", "Bloqueado por direitos autorais nesta região ou plataforma."),
        ("blocked the uploader", "Este vídeo não permite reprodução fora do YouTube."),
        ("not made this video available", "O autor não liberou este vídeo na sua região."),
        ("does not pass filter", f"O vídeo ultrapassa o limite de duração ({YOUTUBE_MAX_DURATION_SEC}s) ou o formato não é permitido aqui."),
        ("requested format is not available", "Não foi encontrado um formato de mídia compatível para baixar."),
        ("unable to download", "Não foi possível baixar o arquivo. Tente outra rede ou mais tarde."),
    ]
    for needle, friendly in rules:
        if needle in msg:
            return friendly
    return (
        "Não foi possível acessar este vídeo. "
        "Este vídeo exige confirmação do YouTube. Você ainda pode baixar o arquivo manualmente e enviar aqui para transcrição."
    )


def resolve_cookiefile(work: Path) -> Path | None:
    """
    Ordem: COOKIES_FILE (caminho absoluto a Netscape) → cookies do navegador (browser_cookie3).
    """
    work.mkdir(parents=True, exist_ok=True)
    ext = os.getenv("COOKIES_FILE", "").strip()
    if ext:
        src = Path(ext).expanduser()
        if src.is_file():
            dest = work / "cookies_imported.txt"
            shutil.copy2(src, dest)
            return dest
    if os.getenv("USE_BROWSER_COOKIES", "1").lower() in ("0", "false", "no"):
        return None
    dest = work / "cookies_browser.txt"
    if write_youtube_cookies(dest):
        return dest
    return None


def _title_slug(info: dict[str, Any]) -> str:
    title = info.get("title") or info.get("id") or "youtube"
    title = re.sub(r"[\n\r\t]+", " ", str(title))
    title = re.sub(r'[<>:"/\\|?*]+', "", title).strip() or "youtube"
    return title[:120]


def _base_opts(work: Path, cookiefile: Path | None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "outtmpl": str(work / "out.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "match_filter": match_filter_func(f"duration <= {YOUTUBE_MAX_DURATION_SEC}"),
        "max_filesize": YOUTUBE_MAX_DOWNLOAD_BYTES,
        "socket_timeout": 90,
        "retries": 3,
    }
    if cookiefile and cookiefile.is_file():
        opts["cookiefile"] = str(cookiefile)
    return opts


def _run_download(url: str, work: Path, opts_extra: dict[str, Any], cookiefile: Path | None) -> dict[str, Any]:
    opts = {**_base_opts(work, cookiefile), **opts_extra}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url.strip(), download=True)
    except DownloadError as e:
        raise ValueError(map_youtube_error(str(e))) from e


def _pick_output_file(work: Path) -> Path:
    skip = {
        "cookies_browser.txt",
        "cookies_imported.txt",
        "cookies.txt",
    }
    files = [
        p
        for p in work.iterdir()
        if p.is_file()
        and p.name not in skip
        and not p.name.endswith((".part", ".ytdl", ".tmp"))
    ]
    if not files:
        raise RuntimeError("Nenhum arquivo foi gerado após o download.")
    return max(files, key=lambda p: p.stat().st_size)


def _output_path_from_info(info: dict[str, Any], work: Path) -> Path:
    fp = info.get("filepath")
    if fp:
        p = Path(fp)
        if p.is_file():
            return p
    return _pick_output_file(work)


def download_youtube_video(url: str, work: Path, cookiefile: Path | None) -> tuple[Path, str]:
    info = _run_download(
        url,
        work,
        {
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        },
        cookiefile,
    )
    path = _output_path_from_info(info, work)
    ext = path.suffix.lower() or ".mp4"
    name = f"{_title_slug(info)}{ext}"
    return path, name


def download_youtube_audio_mp3(url: str, work: Path, cookiefile: Path | None) -> tuple[Path, str]:
    info = _run_download(
        url,
        work,
        {
            "format": "ba/bestaudio/b",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        },
        cookiefile,
    )
    path = _output_path_from_info(info, work)
    if path.suffix.lower() != ".mp3":
        path = _pick_output_file(work)
    name = f"{_title_slug(info)}.mp3"
    return path, name


def download_youtube_bestaudio_raw(url: str, work: Path, cookiefile: Path | None) -> Path:
    _run_download(
        url,
        work,
        {
            "format": "ba/bestaudio/b",
        },
        cookiefile,
    )
    return _pick_output_file(work)


def youtube_url_to_wav(url: str, work: Path, cookiefile: Path | None = None) -> tuple[Path, Path]:
    if not is_allowed_youtube_url(url):
        raise ValueError("URL não é de um vídeo do YouTube permitido.")
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg não está instalado no servidor.")
    cf = resolve_cookiefile(work) if cookiefile is None else cookiefile
    downloaded = download_youtube_bestaudio_raw(url, work, cf)
    wav_path = work / f"{downloaded.stem}_{int(time.time() * 1000)}_16k.wav"
    extract_audio_for_whisper(downloaded, wav_path, timeout_sec=300)
    return wav_path, downloaded
