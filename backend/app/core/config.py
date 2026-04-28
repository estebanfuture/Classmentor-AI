import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]

# Carga backend/.env si existe. Si no existe, la app sigue arrancando.
try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    # En un entorno sin dependencias instaladas, FastAPI no debe romper por config.
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_TRANSCRIPTION_MODEL = os.getenv(
    "OPENAI_TRANSCRIPTION_MODEL",
    "gpt-4o-mini-transcribe",
)
TRANSCRIPTION_PROVIDER = os.getenv("TRANSCRIPTION_PROVIDER", "openai")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
