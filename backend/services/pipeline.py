"""Pipeline completo: transcrição → pós-processamento → resumo."""

from __future__ import annotations

from services.postprocess import polish_transcript
from services.summarizer import summarize
from services.transcriber import transcribe_full


def process_audio(audio_path: str) -> dict:
    raw, segments = transcribe_full(audio_path)
    texto = polish_transcript(raw, segments)
    summary = summarize(texto)
    return {
        "texto": texto,
        "resumo": summary["resumo"],
        "topicos": summary["topicos"],
        "palavras_chave": summary["palavras_chave"],
        "estudo": summary["estudo"],
    }
