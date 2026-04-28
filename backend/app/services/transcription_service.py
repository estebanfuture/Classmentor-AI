from pathlib import Path
from typing import Any

from app.core.config import OPENAI_API_KEY, OPENAI_TRANSCRIPTION_MODEL


BACKEND_DIR = Path(__file__).resolve().parents[2]


def resolve_backend_path(path_value: str) -> Path:
    """Convierte rutas tipo backend/audio/audio.wav en rutas reales del disco."""
    path = Path(path_value)

    if path.is_absolute() or path.exists():
        return path

    # Si la ruta empieza por backend/, la resolvemos desde la raiz del proyecto.
    if path.parts and path.parts[0] == "backend":
        return BACKEND_DIR.parent / path

    # Si la ruta es relativa, asumimos que vive dentro de backend/.
    return BACKEND_DIR / path


def response_to_dict(response: Any) -> dict:
    """Convierte la respuesta del SDK de OpenAI a un dict serializable."""
    if hasattr(response, "model_dump"):
        return response.model_dump()

    if isinstance(response, dict):
        return response

    return {"text": getattr(response, "text", ""), "raw": str(response)}


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe un archivo de audio con OpenAI y devuelve texto + respuesta cruda."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "Falta OPENAI_API_KEY. Crea backend/.env y define OPENAI_API_KEY."
        )

    try:
        from openai import OpenAI, OpenAIError
    except ImportError as exc:
        raise RuntimeError(
            "La libreria openai no esta instalada. Ejecuta pip install -r requirements.txt."
        ) from exc

    resolved_audio_path = resolve_backend_path(audio_path)

    if not resolved_audio_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {audio_path}")

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        with resolved_audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=OPENAI_TRANSCRIPTION_MODEL,
                file=audio_file,
                response_format="json",
            )
    except OpenAIError as exc:
        raise RuntimeError(f"Error de OpenAI API al transcribir audio: {exc}") from exc

    raw_response = response_to_dict(response)
    text = raw_response.get("text", "")

    return {
        "text": text,
        "raw_response": raw_response,
    }
