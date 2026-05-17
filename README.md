# Audio → Texto (MVP)

Upload de **áudio** (mp3, wav, m4a) ou **vídeo** (mp4, webm, mkv, mov, avi…); vídeos têm o áudio extraído com **ffmpeg** no servidor antes da transcrição (Whisper).

## Estrutura

- `backend/` — FastAPI, limite 15 MB, áudio e vídeo (áudio extraído com ffmpeg), rate limit 5/hora por IP, arquivos apagados após processar.
- `frontend/` — HTML, CSS e JS estáticos (compatível com Vercel).

## Cursor (Windows + WSL)

1. **Arquivo → Abrir espaço de trabalho a partir de arquivo…** e escolha `audio-texto.code-workspace` (na raiz deste projeto). Assim o terminal padrão no Windows passa a ser **WSL** e as tasks encontram `backend/`.
2. **Terminal → Executar tarefa…** (ou `Ctrl+Shift+B` se associar à tarefa padrão) → **Audio-Texto: Backend (uvicorn)**.
3. Para o site estático: **Executar tarefa…** → **Audio-Texto: Frontend (HTTP)** e abra `http://127.0.0.1:8080`.

Não use “Executar arquivo Python” no `main.py` com o interpretador do Windows em cima de arquivos do WSL; use a tarefa ou `bash backend/dev.sh` no terminal WSL.

## Backend (local)

Requer **Python 3.10+** e **ffmpeg** instalado no sistema (`ffmpeg -version`).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-whisper.txt --no-build-isolation
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

O `openai-whisper` compila a partir do código-fonte; o `pip` usa um ambiente de build isolado que às vezes não tem `pkg_resources`. Instalar o Whisper com `--no-build-isolation` (depois de `setuptools`/`wheel` já instalados por `requirements.txt`) evita o erro *No module named 'pkg_resources'* no `setup.py` do Whisper.

Variáveis opcionais:

- `ALLOWED_ORIGINS` — lista separada por vírgulas (origens do front na Vercel).
- `WHISPER_MODEL` — padrão `base` (melhor português que `tiny`). `small`/`medium` melhoram ainda mais, com mais RAM e tempo.
- `WHISPER_INITIAL_PROMPT` — texto curto que orienta ortografia e estilo (padrão: transcrição fiel em pt-BR).
- `WHISPER_NO_SPEECH_THRESHOLD` — padrão `0.65` (um pouco acima do padrão do Whisper para reduzir invenção em silêncio/ruído).
- `WHISPER_FP16` — defina `0` se precisar forçar precisão em GPU problemática.

## Frontend

1. Em `frontend/script.js`, defina `API_BASE` com a URL HTTPS do backend em produção.
2. Sirva os arquivos (Live Server, `python -m http.server`, ou deploy na Vercel).

## Deploy (notas)

- **Render/Railway**: configure build para instalar **ffmpeg**; o primeiro download do modelo Whisper pode ser lento e consumir RAM — em planos pequenos use `WHISPER_MODEL=base` ou `tiny` só se precisar economizar RAM (pior qualidade em PT).
- **CORS**: defina `ALLOWED_ORIGINS` com a URL exata do site na Vercel.
- **Rate limit**: a implementação atual é em memória por instância (adequada para um MVP com um worker).
