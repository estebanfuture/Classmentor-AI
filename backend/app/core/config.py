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
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision")
MAX_FRAMES_TO_ANALYZE = int(os.getenv("MAX_FRAMES_TO_ANALYZE", "30"))
STUDY_PROVIDER = os.getenv("STUDY_PROVIDER", "ollama")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "deepseek-r1-14b-16k:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
