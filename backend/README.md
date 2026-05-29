# 🎙️ Audio Texto AI

Projeto desenvolvido para transformar áudios em texto utilizando Inteligência Artificial.

## 🚀 Funcionalidades

- Upload de arquivos de áudio
- Transcrição automática com Whisper AI
- Geração de resumo
- Extração de tópicos principais
- Identificação de palavras-chave
- Criação de material de estudo

## 🛠️ Tecnologias

- Python
- FastAPI
- OpenAI Whisper
- FFmpeg
- Uvicorn
- HTML
- CSS
- JavaScript

## 📂 Estrutura do Projeto

```text
audio-texto/
│
├── backend/
├── frontend/
├── uploads/
├── README.md
└── requirements.txt
```

## ⚙️ Instalação

Clone o projeto:

```bash
git clone URL_DO_REPOSITORIO
```

Entre na pasta:

```bash
cd audio-texto/backend
```

Crie o ambiente virtual:

```bash
python -m venv .venv
```

Ative:

```bash
source .venv/bin/activate
```

Instale dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
uvicorn main:app --reload
```

## 📡 Endpoint Principal

### Upload de áudio

```http
POST /transcribe/file
```

Retorna:

```json
{
  "texto": "...",
  "resumo": "...",
  "topicos": [],
  "palavras_chave": [],
  "estudo": "..."
}
```

## 🎯 Objetivo

Automatizar a transformação de gravações de voz em conteúdo organizado para estudo e consulta.
# 🎙️ Audio Texto AI

Projeto desenvolvido para transformar áudios em texto utilizando Inteligência Artificial.

## 🚀 Funcionalidades

- Upload de arquivos de áudio
- Transcrição automática com Whisper AI
- Geração de resumo
- Extração de tópicos principais
- Identificação de palavras-chave
- Criação de material de estudo

## 🛠️ Tecnologias

- Python
- FastAPI
- OpenAI Whisper
- FFmpeg
- Uvicorn
- HTML
- CSS
- JavaScript

## 📂 Estrutura do Projeto

```text
audio-texto/
│
├── backend/
├── frontend/
├── uploads/
├── README.md
└── requirements.txt
```

## ⚙️ Instalação

Clone o projeto:

```bash
git clone URL_DO_REPOSITORIO
```

Entre na pasta:

```bash
cd audio-texto/backend
```

Crie o ambiente virtual:

```bash
python -m venv .venv
```

Ative:

```bash
source .venv/bin/activate
```

Instale dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
uvicorn main:app --reload
```

## 📡 Endpoint Principal

### Upload de áudio

```http
POST /transcribe/file
```

Retorna:

```json
{
  "texto": "...",
  "resumo": "...",
  "topicos": [],
  "palavras_chave": [],
  "estudo": "..."
}
```

## 🎯 Objetivo

Automatizar a transformação de gravações de voz em conteúdo organizado para estudo e consulta.


## 👩‍💻 Desenvolvido por

Milena Fernanda 

