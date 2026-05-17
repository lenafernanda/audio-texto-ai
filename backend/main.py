import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from services.export_docs import build_docx, build_pdf, build_txt
from services.media import (
    VIDEO_SUFFIXES,
    extract_audio_for_whisper,
    ffmpeg_available,
    is_video,
)
from services.pipeline import process_audio
from services.youtube_ops import (
    download_youtube_audio_mp3,
    download_youtube_video,
    download_youtube_bestaudio_raw,
    is_allowed_media_url,
    is_allowed_youtube_url,
    resolve_cookiefile,
    yt_dlp_available,
)

MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".opus"}
ALLOWED_SUFFIXES = AUDIO_SUFFIXES | VIDEO_SUFFIXES
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "8"))
RATE_WINDOW_SEC = 3600

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_rate_buckets: dict[str, list[float]] = defaultdict(list)

app = FastAPI(title="Texto Inteligente — transcrição e resumo")

_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,http://127.0.0.1:8080",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS", "GET"],
    allow_headers=["*"],
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(ip: str) -> None:
    now = time.time()
    bucket = _rate_buckets[ip]
    bucket[:] = [t for t in bucket if now - t < RATE_WINDOW_SEC]
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Você atingiu o limite de uso por hora. Tente novamente mais tarde.",
        )
    bucket.append(now)


def _guess_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
    }.get(ext, "application/octet-stream")


def _safe_rmtree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _json_result(data: dict) -> JSONResponse:
    return JSONResponse(data)


async def _prepare_audio_from_upload(dest: Path, suffix: str) -> tuple[Path, list[Path]]:
    """Retorna caminho pronto para o Whisper e lista de arquivos temporários a apagar."""
    cleanup = [dest]
    if suffix == ".wav":
        return dest, cleanup
    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="O servidor precisa do ffmpeg para processar este arquivo.",
        )
    wav_path = dest.parent / f"{dest.stem}_16k.wav"
    try:
        extract_audio_for_whisper(dest, wav_path)
    except subprocess.CalledProcessError:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível extrair o áudio. Verifique se o arquivo tem som.",
        ) from None
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="O processamento demorou demais. Tente um arquivo menor.",
        ) from None
    cleanup.append(wav_path)
    return wav_path, cleanup


async def _transcribe_path(path: Path) -> dict:
    return await asyncio.to_thread(process_audio, str(path))


@app.get("/health")
async def health():
    return {"ok": True, "whisper_model": os.getenv("WHISPER_MODEL", "small")}


@app.post("/transcribe/file")
async def transcribe_file(request: Request, file: UploadFile = File(...)):
    ip = _client_ip(request)
    _enforce_rate_limit(ip)

    filename = file.filename or "gravacao.webm"
    suffix = Path(filename).suffix.lower() or ".webm"
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Envie áudio (mp3, wav, m4a, webm) ou vídeo (mp4, webm, mov…).",
        )

    dest = UPLOAD_DIR / f"{int(time.time() * 1000)}_{Path(filename).name}"
    cleanup: list[Path] = []
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    mb = MAX_BYTES // (1024 * 1024)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Arquivo muito grande. O limite é {mb} MB.",
                    )
                out.write(chunk)

        audio_path, cleanup = await _prepare_audio_from_upload(dest, suffix)
        data = await _transcribe_path(audio_path)
        return _json_result(data)
    finally:
        for p in cleanup:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass


class TranscribeUrlBody(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)


@app.post("/transcribe/url")
async def transcribe_url(request: Request, body: TranscribeUrlBody):
    ip = _client_ip(request)
    _enforce_rate_limit(ip)

    raw = body.url.strip()
    if not is_allowed_media_url(raw):
        raise HTTPException(
            status_code=400,
            detail="Informe um link público válido (começando com http:// ou https://).",
        )
    if not yt_dlp_available():
        raise HTTPException(
            status_code=503,
            detail="Serviço temporariamente indisponível. Tente enviar o arquivo manualmente.",
        )
    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="Serviço temporariamente indisponível. Tente enviar o arquivo manualmente.",
        )

    work = UPLOAD_DIR / f"url_{int(time.time() * 1000)}"
    work.mkdir(parents=True, exist_ok=False)
    cookiefile = resolve_cookiefile(work) if is_allowed_youtube_url(raw) else None
    wav_path: Path | None = None
    try:
        downloaded = await asyncio.to_thread(
            download_youtube_bestaudio_raw, raw, work, cookiefile
        )
        wav_path = work / f"{downloaded.stem}_16k.wav"
        await asyncio.to_thread(extract_audio_for_whisper, downloaded, wav_path)
        data = await _transcribe_path(wav_path)
        return _json_result(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (TimeoutError, subprocess.TimeoutExpired):
        raise HTTPException(
            status_code=408,
            detail="O link demorou demais para processar. Tente um vídeo mais curto ou envie o arquivo.",
        ) from None
    except subprocess.CalledProcessError:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível extrair o áudio deste link. Envie o arquivo manualmente.",
        ) from None
    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível acessar este link. Baixe o arquivo e envie aqui para transcrever.",
        ) from None
    finally:
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)


class ExportBody(BaseModel):
    formato: Literal["txt", "pdf", "docx"]
    texto: str = ""
    resumo: str = ""
    estudo: str = ""
    titulo: str = "Transcrição"


def _attachment_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/export")
async def export_document(body: ExportBody):
    titulo = (body.titulo or "Transcrição")[:120]
    if body.formato == "txt":
        return _attachment_response(
            build_txt(body.texto, body.resumo, body.estudo),
            "text/plain; charset=utf-8",
            "conteudo.txt",
        )
    if body.formato == "pdf":
        return _attachment_response(
            build_pdf(body.texto, body.resumo, body.estudo, titulo),
            "application/pdf",
            "conteudo.pdf",
        )
    return _attachment_response(
        build_docx(body.texto, body.resumo, body.estudo, titulo),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "conteudo.docx",
    )


class DownloadBody(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    action: Literal["video", "audio"]


@app.post("/download")
async def download_media(
    request: Request,
    body: DownloadBody,
    background_tasks: BackgroundTasks,
):
    """Função complementar: baixar vídeo ou áudio (não é o foco do produto)."""
    ip = _client_ip(request)
    _enforce_rate_limit(ip)

    raw = body.url.strip()
    if not is_allowed_youtube_url(raw):
        raise HTTPException(
            status_code=400,
            detail="Downloads rápidos funcionam melhor com links do YouTube. Para outros sites, use transcrição por link.",
        )
    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="Download indisponível no momento. Você ainda pode transcrever enviando o arquivo.",
        )

    work = UPLOAD_DIR / f"dl_{int(time.time() * 1000)}"
    work.mkdir(parents=True, exist_ok=False)
    cookiefile = resolve_cookiefile(work)
    try:
        if body.action == "video":
            path, filename = await asyncio.to_thread(
                download_youtube_video, raw, work, cookiefile
            )
        else:
            path, filename = await asyncio.to_thread(
                download_youtube_audio_mp3, raw, work, cookiefile
            )
    except ValueError as e:
        _safe_rmtree(work)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (TimeoutError, subprocess.TimeoutExpired):
        _safe_rmtree(work)
        raise HTTPException(
            status_code=408,
            detail="O download demorou demais. Tente um vídeo mais curto.",
        ) from None
    except RuntimeError as e:
        _safe_rmtree(work)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except subprocess.CalledProcessError:
        _safe_rmtree(work)
        raise HTTPException(
            status_code=400,
            detail="Não foi possível baixar este conteúdo. Tente enviar o arquivo para transcrição.",
        ) from None

    background_tasks.add_task(_safe_rmtree, work)
    return FileResponse(
        str(path),
        filename=filename,
        media_type=_guess_media_type(path),
    )


# Compatibilidade com frontend antigo
@app.post("/upload")
async def upload_legacy(request: Request, file: UploadFile = File(...)):
    return await transcribe_file(request, file)


class YouTubeLegacy(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    action: Literal["video", "audio", "transcribe"]


@app.post("/youtube")
async def youtube_legacy(
    request: Request,
    body: YouTubeLegacy,
    background_tasks: BackgroundTasks,
):
    if body.action == "transcribe":
        return await transcribe_url(request, TranscribeUrlBody(url=body.url))
    return await download_media(
        request,
        DownloadBody(url=body.url, action=body.action),
        background_tasks,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
