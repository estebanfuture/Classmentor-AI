import base64
import json
from pathlib import Path

import httpx

from app.core.config import OLLAMA_BASE_URL, OLLAMA_VISION_MODEL


BACKEND_DIR = Path(__file__).resolve().parents[2]
VISION_PROMPT_PATH = BACKEND_DIR / "app" / "prompts" / "vision_prompt.txt"


class VisionServiceError(RuntimeError):
    """Error base para problemas del analisis visual."""


class OllamaConnectionError(VisionServiceError):
    """Ollama no esta disponible o no responde."""


class OllamaModelNotFoundError(VisionServiceError):
    """El modelo de vision configurado no existe en Ollama."""


class InvalidVisionJSONError(VisionServiceError):
    """El modelo respondio algo que no se puede parsear como JSON."""

    def __init__(self, message: str, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


def resolve_backend_path(path_value: str) -> Path:
    """Convierte rutas tipo backend/frames/x.jpg en rutas reales del disco."""
    path = Path(path_value)

    if path.is_absolute() or path.exists():
        return path

    if path.parts and path.parts[0] == "backend":
        return BACKEND_DIR.parent / path

    return BACKEND_DIR / path


def load_vision_prompt() -> str:
    """Lee el prompt usado para analizar una captura."""
    try:
        return VISION_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise VisionServiceError(
            "No se pudo leer backend/app/prompts/vision_prompt.txt."
        ) from exc


def encode_image_base64(image_path: Path) -> str:
    """Lee una imagen y la convierte a base64 para enviarla a Ollama."""
    try:
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        raise VisionServiceError(f"No se pudo leer la imagen: {image_path}") from exc

    return base64.b64encode(image_bytes).decode("utf-8")


def extract_message_content(response_data: dict) -> str:
    """Obtiene el texto devuelto por /api/chat de Ollama."""
    message = response_data.get("message", {})

    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()

    return ""


def is_model_missing_error(status_code: int, response_text: str) -> bool:
    """Detecta el error tipico cuando falta un modelo en Ollama."""
    normalized_text = response_text.lower()

    return (
        status_code == 404
        or "not found" in normalized_text
        or "pull" in normalized_text
    ) and OLLAMA_VISION_MODEL.lower() in normalized_text


def analyze_frame(image_path: str) -> dict:
    """Analiza una captura con Ollama Vision y devuelve un dict Python."""
    resolved_image_path = resolve_backend_path(image_path)

    if not resolved_image_path.exists():
        raise FileNotFoundError(f"No existe la imagen: {image_path}")

    prompt = load_vision_prompt()
    image_base64 = encode_image_base64(resolved_image_path)

    payload = {
        "model": OLLAMA_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "stream": False,
        "format": "json",
    }

    ollama_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    try:
        response = httpx.post(ollama_url, json=payload, timeout=120.0)
    except httpx.ConnectError as exc:
        raise OllamaConnectionError(
            f"Ollama no responde en {OLLAMA_BASE_URL}. Comprueba que este arrancado."
        ) from exc
    except httpx.TimeoutException as exc:
        raise OllamaConnectionError(
            "Ollama tardo demasiado en responder al analisis visual."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaConnectionError(f"Error conectando con Ollama: {exc}") from exc

    response_text = response.text

    if is_model_missing_error(response.status_code, response_text):
        raise OllamaModelNotFoundError(
            f"No se encontro el modelo {OLLAMA_VISION_MODEL}. Ejecuta: "
            f"ollama pull {OLLAMA_VISION_MODEL}"
        )

    if response.status_code >= 400:
        raise VisionServiceError(
            f"Ollama devolvio HTTP {response.status_code}: {response_text}"
        )

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise InvalidVisionJSONError(
            "Ollama no devolvio una respuesta HTTP con JSON valido.",
            response_text,
        ) from exc

    content = extract_message_content(response_data)

    try:
        analysis = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidVisionJSONError(
            "El modelo de vision no devolvio JSON valido en message.content.",
            content or response_text,
        ) from exc

    if not isinstance(analysis, dict):
        raise InvalidVisionJSONError(
            "El modelo de vision devolvio JSON valido, pero no era un objeto.",
            content,
        )

    return analysis


def analyze_frames(frame_paths: list[str], max_frames: int = 30) -> list[dict]:
    """Analiza hasta max_frames capturas y conserva la ruta junto al resultado."""
    selected_frame_paths = frame_paths[:max_frames]
    analyses = []

    for frame_path in selected_frame_paths:
        analyses.append(
            {
                "image_path": frame_path,
                "analysis": analyze_frame(frame_path),
            }
        )

    return analyses
