"""Resumo automático extrativo (sem API paga) para estudo e revisão."""

from __future__ import annotations

import re
from collections import Counter

from services.postprocess import _STOPWORDS, _split_sentences, extract_keywords, tokenize_words


def _sentence_score(sentence: str, freqs: Counter[str]) -> float:
    words = tokenize_words(sentence)
    if not words:
        return 0.0
    score = sum(freqs.get(w, 0) for w in words if w not in _STOPWORDS)
    return score / max(len(words), 1)


def _build_freqs(sentences: list[str]) -> Counter[str]:
    all_words = []
    for s in sentences:
        all_words.extend(w for w in tokenize_words(s) if w not in _STOPWORDS and len(w) > 3)
    return Counter(all_words)


def summarize(text: str) -> dict:
    """
    Retorna resumo curto, tópicos, palavras-chave e versão para estudo.
    """
    flat = re.sub(r"\n+", " ", text).strip()
    sentences = _split_sentences(flat)
    if not sentences:
        sentences = [flat] if flat else []

    keywords = extract_keywords(text, top_n=10)

    if len(sentences) <= 2:
        resumo = " ".join(sentences)
        topicos = sentences[:3]
        estudo = _format_study(resumo, topicos, keywords)
        return {
            "resumo": resumo,
            "topicos": topicos,
            "palavras_chave": keywords,
            "estudo": estudo,
        }

    freqs = _build_freqs(sentences)
    ranked = sorted(
        enumerate(sentences),
        key=lambda x: _sentence_score(x[1], freqs),
        reverse=True,
    )

    n_summary = max(2, min(5, len(sentences) // 4))
    picked_idx = sorted(i for i, _ in ranked[:n_summary])
    resumo_sentences = [sentences[i] for i in picked_idx]
    resumo = " ".join(resumo_sentences)

    n_topics = max(3, min(6, len(sentences) // 6))
    topic_indices = sorted(i for i, _ in ranked[:n_topics])
    topicos = []
    for i in topic_indices:
        s = sentences[i].strip()
        if len(s) > 120:
            s = s[:117].rstrip() + "…"
        topicos.append(s)

    estudo = _format_study(resumo, topicos, keywords)

    return {
        "resumo": resumo,
        "topicos": topicos,
        "palavras_chave": keywords,
        "estudo": estudo,
    }


def _format_study(resumo: str, topicos: list[str], keywords: list[str]) -> str:
    lines = ["📌 Resumo da aula", resumo, "", "📚 Tópicos principais"]
    for i, t in enumerate(topicos, 1):
        lines.append(f"{i}. {t}")
    if keywords:
        lines.extend(["", "🔑 Palavras-chave", ", ".join(keywords)])
    lines.extend(["", "💡 Dica", "Revise os tópicos em ordem e teste-se explicando cada um em voz alta."])
    return "\n".join(lines)
