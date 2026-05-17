"""Pós-processamento do texto transcrito para legibilidade em português."""

from __future__ import annotations

import re
from collections import Counter

# Palavras muito comuns em PT (lista curta para resumo/keywords).
_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "em", "um", "uma", "os", "as", "dos", "das",
    "que", "na", "no", "para", "com", "por", "se", "é", "ao", "à", "como", "mas",
    "ou", "ser", "foi", "são", "mais", "já", "muito", "também", "então", "isso",
    "essa", "esse", "ele", "ela", "eles", "elas", "nós", "você", "vocês", "eu",
    "me", "te", "lhe", "nos", "lhes", "seu", "sua", "seus", "suas", "meu", "minha",
    "um", "uns", "umas", "né", "tipo", "assim", "aí", "lá", "aqui", "bem", "só",
}

_BASIC_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bvoce\b", re.I), "você"),
    (re.compile(r"\bnao\b", re.I), "não"),
    (re.compile(r"\besta\b(?=\s)", re.I), "está"),
    (re.compile(r"\btambem\b", re.I), "também"),
    (re.compile(r"\bporque\b", re.I), "porque"),
    (re.compile(r"\bate\b", re.I), "até"),
    (re.compile(r"\bja\b", re.I), "já"),
    (re.compile(r"\bso\b", re.I), "só"),
    (re.compile(r"\bmais ou menos\b", re.I), "mais ou menos"),
]


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _remove_consecutive_duplicates(text: str) -> str:
    words = text.split()
    if not words:
        return text
    out: list[str] = []
    prev = ""
    for w in words:
        key = re.sub(r"[^\wáàâãéêíóôõúç]", "", w.lower())
        prev_key = re.sub(r"[^\wáàâãéêíóôõúç]", "", prev.lower())
        if key and key == prev_key:
            continue
        out.append(w)
        prev = w
    return " ".join(out)


def _apply_basic_fixes(text: str) -> str:
    for pattern, repl in _BASIC_FIXES:
        text = pattern.sub(repl, text)
    return text


def _capitalize_sentence(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    return s[0].upper() + s[1:]


def _punctuate_sentence(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    if s[-1] not in ".!?…":
        if s.lower().endswith(("né", "não é", "certo")):
            s += "?"
        else:
            s += "."
    return s


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def format_from_segments(segments: list[dict] | None, raw_text: str) -> str:
    """Agrupa segmentos do Whisper em parágrafos naturais."""
    if not segments:
        return format_plain_text(raw_text)

    paragraphs: list[str] = []
    buf: list[str] = []
    last_end = 0.0

    for seg in segments:
        t = (seg.get("text") or "").strip()
        if not t:
            continue
        start = float(seg.get("start") or 0)
        if buf and start - last_end > 2.5:
            paragraphs.append(_join_sentences(buf))
            buf = []
        buf.append(t)
        last_end = float(seg.get("end") or start)

    if buf:
        paragraphs.append(_join_sentences(buf))

    return "\n\n".join(p for p in paragraphs if p)


def _join_sentences(parts: list[str]) -> str:
    text = " ".join(parts)
    text = _collapse_spaces(text)
    text = _remove_consecutive_duplicates(text)
    text = _apply_basic_fixes(text)
    sentences = _split_sentences(text) if re.search(r"[.!?]", text) else [text]
    return " ".join(_punctuate_sentence(_capitalize_sentence(s)) for s in sentences if s)


def format_plain_text(raw: str) -> str:
    text = _collapse_spaces(raw)
    text = _remove_consecutive_duplicates(text)
    text = _apply_basic_fixes(text)

    # Quebra em frases por pausas longas ou pontuação fraca do Whisper.
    chunks = re.split(r"\s{2,}|\s*[,;]\s+", text)
    sentences: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) > 180:
            sub = re.split(r"(?<=[.!?])\s+", chunk)
            sentences.extend(s.strip() for s in sub if s.strip())
        else:
            sentences.append(chunk)

    if not sentences:
        sentences = [text] if text else []

    paragraphs: list[str] = []
    group: list[str] = []
    for i, sent in enumerate(sentences):
        group.append(_punctuate_sentence(_capitalize_sentence(sent)))
        if len(group) >= 4 or (i + 1) % 5 == 0:
            paragraphs.append(" ".join(group))
            group = []
    if group:
        paragraphs.append(" ".join(group))

    return "\n\n".join(paragraphs)


def polish_transcript(raw: str, segments: list[dict] | None = None) -> str:
    if segments:
        return format_from_segments(segments, raw)
    return format_plain_text(raw)


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-záàâãéêíóôõúçA-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9]+", text.lower())


def extract_keywords(text: str, top_n: int = 12) -> list[str]:
    words = [w for w in tokenize_words(text) if len(w) > 3 and w not in _STOPWORDS]
    counts = Counter(words)
    return [w for w, _ in counts.most_common(top_n)]
