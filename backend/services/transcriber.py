import os

import whisper

_model = None


def _model_name() -> str:
    # `small` melhora muito o PT; `medium` exige mais RAM. Evite `tiny` em produção.
    return os.getenv("WHISPER_MODEL", "tiny")


def _initial_prompt() -> str:
    return os.getenv(
        "WHISPER_INITIAL_PROMPT",
        "Fala em português do Brasil. Transcreva literalmente o que foi dito, sem inventar trechos, "
        "sem traduzir para inglês e sem substituir termos por sinônimos em outro idioma. "
        "Use ortografia correta em português.",
    )


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(_model_name())
    return _model


def transcribe(audio_path: str, language: str | None = "pt") -> str:
    model = get_model()
    beam = max(1, int(os.getenv("WHISPER_BEAM_SIZE", "5")))
    kwargs: dict = {
        "language": language,
        "task": "transcribe",
        "temperature": 0,
        # Reduz encadeamento de texto improvável (alucinações em sequência).
        "condition_on_previous_text": False,
        "initial_prompt": _initial_prompt(),
        "no_speech_threshold": float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.6")),
        "compression_ratio_threshold": float(
            os.getenv("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4")
        ),
        "logprob_threshold": float(os.getenv("WHISPER_LOGPROB_THRESHOLD", "-1.0")),
        "beam_size": beam,
    }
    if beam > 1:
        kwargs["patience"] = float(os.getenv("WHISPER_PATIENCE", "1.0"))
    fp16_env = os.getenv("WHISPER_FP16", "").lower()
    if fp16_env in ("0", "false", "no"):
        kwargs["fp16"] = False
    result = model.transcribe(audio_path, **kwargs)
    return (result.get("text") or "").strip()


def transcribe_full(audio_path: str, language: str | None = "pt") -> tuple[str, list[dict]]:
    """Retorna texto bruto e segmentos para pós-processamento."""
    model = get_model()
    beam = max(1, int(os.getenv("WHISPER_BEAM_SIZE", "5")))
    kwargs: dict = {
        "language": language,
        "task": "transcribe",
        "temperature": 0,
        "condition_on_previous_text": False,
        "initial_prompt": _initial_prompt(),
        "no_speech_threshold": float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.6")),
        "compression_ratio_threshold": float(
            os.getenv("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4")
        ),
        "logprob_threshold": float(os.getenv("WHISPER_LOGPROB_THRESHOLD", "-1.0")),
        "beam_size": beam,
    }
    if beam > 1:
        kwargs["patience"] = float(os.getenv("WHISPER_PATIENCE", "1.0"))
    fp16_env = os.getenv("WHISPER_FP16", "").lower()
    if fp16_env in ("0", "false", "no"):
        kwargs["fp16"] = False
    result = model.transcribe(audio_path, **kwargs)
    raw = (result.get("text") or "").strip()
    segments = result.get("segments") or []
    return raw, segments
