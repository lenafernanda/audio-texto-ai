"""Exporta cookies do navegador para formato Netscape (compatível com yt-dlp)."""

from __future__ import annotations

from pathlib import Path


def write_youtube_cookies(dest: Path) -> bool:
    """
    Tenta ler cookies do YouTube de navegadores comuns (browser_cookie3).
    Retorna True se criou um arquivo com conteúdo útil.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        import browser_cookie3
    except ImportError:
        return False

    jar = None
    for name in ("chrome", "chromium", "brave", "firefox", "edge"):
        loader = getattr(browser_cookie3, name, None)
        if not callable(loader):
            continue
        try:
            jar = loader(domain_name=".youtube.com")
            if jar:
                break
        except Exception:
            continue

    if jar is None:
        return False

    lines = ["# Netscape HTTP Cookie File\n"]
    for c in jar:
        domain = c.domain or ""
        include_sub = "TRUE" if str(domain).startswith(".") else "FALSE"
        path = c.path or "/"
        secure = "TRUE" if c.secure else "FALSE"
        expires = int(c.expires) if getattr(c, "expires", None) else 0
        name = c.name or ""
        value = getattr(c, "value", "") or ""
        lines.append(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

    text = "".join(lines)
    if len(text) < 80:
        return False
    dest.write_text(text, encoding="utf-8")
    return True
