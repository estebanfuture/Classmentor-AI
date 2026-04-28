import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]

# Carga backend/.env si existe. Si no existe, la app sigue arrancando.
load_dotenv(BACKEND_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_TRANSCRIPTION_MODEL = os.getenv(
    "OPENAI_TRANSCRIPTION_MODEL",
    "gpt-4o-mini-transcribe",
)
