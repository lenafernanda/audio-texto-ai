#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Whisper: build do sdist precisa de setuptools no mesmo ambiente (evita pkg_resources no build isolado)
pip install -r requirements-whisper.txt --no-build-isolation
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
