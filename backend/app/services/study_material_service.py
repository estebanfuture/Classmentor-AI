import json
import re
from pathlib import Path

import httpx

from app.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_TEXT_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
STUDY_MATERIALS_PROMPT_PATH = (
    BACKEND_DIR / "app" / "prompts" / "study_materials_prompt.txt"
)


class StudyMaterialServiceError(RuntimeError):
    """Error base para problemas generando materiales de estudio."""


class StudyOllamaConnectionError(StudyMaterialServiceError):
    """Ollama no esta disponible o no responde."""


class StudyOllamaModelNotFoundError(StudyMaterialServiceError):
    """El modelo de texto configurado no existe en Ollama."""


def load_study_materials_prompt() -> str:
    """Lee el prompt usado para generar materiales de estudio."""
    try:
        return STUDY_MATERIALS_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise StudyMaterialServiceError(
            "No se pudo leer backend/app/prompts/study_materials_prompt.txt."
        ) from exc


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
    model_name = OLLAMA_TEXT_MODEL.lower()

    return (
        status_code == 404
        or "not found" in normalized_text
        or "pull" in normalized_text
    ) and (model_name in normalized_text or "model" in normalized_text)


def remove_thinking_blocks(markdown: str) -> str:
    """Elimina bloques <think> si un modelo razonador los incluye por error."""
    cleaned_markdown = re.sub(
        r"<think>.*?</think>",
        "",
        markdown,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if cleaned_markdown.lower().startswith("<think"):
        first_heading_index = cleaned_markdown.find("#")

        if first_heading_index >= 0:
            cleaned_markdown = cleaned_markdown[first_heading_index:]

    cleaned_markdown = cleaned_markdown.replace("<think>", "").replace("</think>", "")

    return cleaned_markdown.strip()


def remove_outer_markdown_fence(markdown: str) -> str:
    """Quita solo el bloque ```markdown externo que a veces envuelve todo."""
    cleaned_markdown = markdown.strip()
    lines = cleaned_markdown.splitlines()

    if not lines:
        return cleaned_markdown

    first_line = lines[0].strip().lower()

    if first_line in ("```markdown", "```"):
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

    return "\n".join(lines).strip()


def clean_unexpected_foreign_characters(markdown: str) -> str:
    """Quita caracteres de alfabetos no esperados sin tocar Markdown o comandos."""
    cleaned_markdown = re.sub(
        r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0400-\u04FF]+\s*",
        "",
        markdown,
    )
    cleaned_markdown = re.sub(r"[\u200B-\u200D\uFEFF\uFFFD]", "", cleaned_markdown)

    replacements = {
        "snapshot": "captura del estado",
        "staged changes": "cambios preparados",
        "version control": "control de versiones",
    }

    for source, target in replacements.items():
        cleaned_markdown = re.sub(
            rf"\b{re.escape(source)}\b",
            target,
            cleaned_markdown,
            flags=re.IGNORECASE,
        )

    lines = [line.rstrip() for line in cleaned_markdown.splitlines()]

    return "\n".join(lines).strip()


def build_user_message(
    class_id: str,
    transcript_data: dict,
    vision_data: dict | None,
) -> str:
    """Construye el mensaje con los datos de la clase para Ollama."""
    data = {
        "class_id": class_id,
        "transcript_data": transcript_data,
        "vision_data": vision_data,
    }

    return (
        "Genera el material de estudio para esta clase usando estos datos JSON.\n"
        "Si vision_data es null o no aporta informacion, usa principalmente "
        "transcript_data.\n\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )


def generate_study_materials(
    class_id: str,
    transcript_data: dict,
    vision_data: dict | None,
) -> str:
    """Genera materiales de estudio en Markdown usando Ollama local."""
    prompt = load_study_materials_prompt()
    user_message = build_user_message(class_id, transcript_data, vision_data)

    payload = {
        "model": OLLAMA_TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "stream": False,
    }

    ollama_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    try:
        response = httpx.post(
            ollama_url,
            json=payload,
            timeout=float(OLLAMA_TIMEOUT_SECONDS),
        )
    except httpx.ConnectError as exc:
        raise StudyOllamaConnectionError(
            f"Ollama no responde en {OLLAMA_BASE_URL}. Comprueba que este arrancado."
        ) from exc
    except httpx.TimeoutException as exc:
        raise StudyOllamaConnectionError(
            "Ollama tardo demasiado en generar los materiales de estudio."
        ) from exc
    except httpx.HTTPError as exc:
        raise StudyOllamaConnectionError(f"Error conectando con Ollama: {exc}") from exc

    response_text = response.text

    if is_model_missing_error(response.status_code, response_text):
        raise StudyOllamaModelNotFoundError(
            "No se encontro el modelo "
            f"{OLLAMA_TEXT_MODEL}. Ejecuta: ollama pull deepseek-r1-14b-16k"
        )

    if response.status_code >= 400:
        raise StudyMaterialServiceError(
            f"Ollama devolvio HTTP {response.status_code}: {response_text}"
        )

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise StudyMaterialServiceError(
            "Ollama no devolvio una respuesta HTTP con JSON valido."
        ) from exc

    markdown = extract_message_content(response_data)

    if not markdown:
        raise StudyMaterialServiceError(
            "Ollama respondio correctamente, pero no devolvio contenido Markdown."
        )

    cleaned_markdown = remove_thinking_blocks(markdown)
    cleaned_markdown = remove_outer_markdown_fence(cleaned_markdown)

    return clean_unexpected_foreign_characters(cleaned_markdown)
