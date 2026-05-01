import json
import re
from pathlib import Path

import httpx

from app.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_TEXT_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)
from app.services.knowledge_retriever_service import load_topic_pack
from app.services.quality_guard_service import apply_quality_guard
from app.services.teaching_plan_service import build_teaching_plan
from app.services.topic_detector_service import detect_topic
from app.services.transcript_normalizer_service import (
    normalize_transcript_terms as normalize_terms_with_topic_pack,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
STUDY_MATERIALS_PROMPT_PATH = (
    BACKEND_DIR / "app" / "prompts" / "study_materials_prompt.txt"
)
PEDAGOGY_PROFILE_PATH = BACKEND_DIR / "app" / "prompts" / "pedagogy_profile.txt"

STUDY_SECTION_DEFINITIONS = [
    ("human_summary", "## 1. Resumen en lenguaje humano"),
    ("class_goal", "## 2. Qué intentaba enseñar la clase"),
    ("seen_in_class", "## 3. Visto en clase"),
    ("verified_reinforcement", "## 4. Refuerzo verificado"),
    ("explanation_from_zero", "## 5. Explicación desde cero"),
    ("visual_examples", "## 6. Ejemplos visuales en texto"),
    ("code_commands_errors", "## 7. Código, comandos o errores vistos"),
    ("confusing_parts", "## 8. Partes que podrían quedar confusas"),
    ("prerequisites", "## 9. Prerrequisitos recomendados"),
    ("micro_challenges", "## 10. Micro-retos prácticos"),
    ("review_questions", "## 11. Preguntas de repaso"),
    ("study_plan", "## 12. Plan de estudio"),
    ("transcription_errors", "## Posibles errores de transcripción"),
]

class StudyMaterialServiceError(RuntimeError):
    """Error base para problemas generando materiales de estudio."""


class StudyOllamaConnectionError(StudyMaterialServiceError):
    """Ollama no esta disponible o no responde."""


class StudyOllamaModelNotFoundError(StudyMaterialServiceError):
    """El modelo de texto configurado no existe en Ollama."""


def load_study_materials_prompt() -> str:
    """Lee el prompt usado para generar materiales de estudio."""
    try:
        pedagogy_profile = PEDAGOGY_PROFILE_PATH.read_text(encoding="utf-8")
        study_prompt = STUDY_MATERIALS_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise StudyMaterialServiceError(
            "No se pudieron leer los prompts de materiales de estudio."
        ) from exc

    return f"{pedagogy_profile}\n\n---\n\n{study_prompt}"


def build_topic_prompt_context(topic_info: dict, topic_pack: dict | None) -> str:
    """Construye contexto de tema y conocimiento verificado para el prompt."""
    topic = topic_info.get("topic", "unknown")
    confidence = topic_info.get("confidence", "low")
    detected_keywords = topic_info.get("detected_keywords", [])
    lines = [
        "Contexto detectado por ClassMentor Teaching Algorithm v0.1:",
        f"- Tema detectado: {topic}",
        f"- Confianza: {confidence}",
        f"- Palabras detectadas: {', '.join(detected_keywords) or 'ninguna'}",
    ]

    if topic == "git" and topic_pack:
        concepts = topic_pack.get("canonical_concepts", {})
        lines.append("")
        lines.append("Conocimiento verificado de Git que debes respetar:")

        for term, explanation in concepts.items():
            lines.append(f"- {term}: {explanation}")

    return "\n".join(lines)


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

    if first_line in ("```markdown", "```json", "```"):
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


def clean_study_markdown(
    markdown: str,
    topic: str | None = None,
    topic_pack: dict | None = None,
) -> str:
    """Aplica correcciones pedagogicas simples sin romper bloques de codigo."""
    markdown = clean_unexpected_foreign_characters(markdown)

    return apply_quality_guard(markdown, topic=topic, topic_pack=topic_pack)


def parse_study_sections(raw_content: str) -> dict:
    """Convierte la respuesta de Ollama en secciones estructuradas."""
    cleaned_content = remove_outer_markdown_fence(remove_thinking_blocks(raw_content))

    try:
        parsed_content = json.loads(cleaned_content)
    except json.JSONDecodeError:
        json_start = cleaned_content.find("{")
        json_end = cleaned_content.rfind("}")

        if json_start >= 0 and json_end > json_start:
            try:
                parsed_content = json.loads(cleaned_content[json_start:json_end + 1])
            except json.JSONDecodeError:
                return build_fallback_sections(cleaned_content)
        else:
            return build_fallback_sections(cleaned_content)

    if not isinstance(parsed_content, dict):
        return build_fallback_sections(cleaned_content)

    return parsed_content


def build_fallback_sections(raw_content: str) -> dict:
    """Fallback si el modelo no devuelve JSON valido."""
    return {
        "title": "Material de estudio",
        "human_summary": raw_content.strip() or "No se pudo generar un resumen claro.",
        "class_goal": "Revisar el contenido detectado en la clase.",
        "seen_in_class": "Contenido generado a partir de la transcripción disponible.",
        "verified_reinforcement": "No se pudo leer una respuesta estructurada; se conserva el contenido disponible de forma controlada.",
        "explanation_from_zero": "",
        "visual_examples": "",
        "code_commands_errors": "",
        "confusing_parts": "",
        "prerequisites": "",
        "micro_challenges": "",
        "review_questions": "",
        "study_plan": "",
        "transcription_errors": "",
    }


def strip_unwanted_headings(text: str) -> str:
    """Evita que el contenido del modelo cree titulos fuera de la plantilla."""
    cleaned_lines = []

    for line in text.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("#"):
            stripped_line = stripped_line.lstrip("#").strip()

        cleaned_lines.append(stripped_line if line.strip().startswith("#") else line)

    return "\n".join(cleaned_lines).strip()


def format_section_content(value) -> str:
    """Convierte strings, listas o dicts simples a Markdown interno."""
    if value is None:
        return ""

    if isinstance(value, list):
        lines = []

        for item in value:
            if isinstance(item, dict):
                item_text = json.dumps(item, ensure_ascii=False)
            else:
                item_text = str(item)

            if item_text.strip():
                lines.append(f"- {strip_unwanted_headings(item_text)}")

        return "\n".join(lines).strip()

    if isinstance(value, dict):
        lines = []

        for key, item in value.items():
            label = str(key).replace("_", " ").strip()
            item_text = format_section_content(item)

            if item_text:
                lines.append(f"- {label}: {item_text}")

        return "\n".join(lines).strip()

    return strip_unwanted_headings(str(value))


def render_study_material_markdown(sections: dict) -> str:
    """Renderiza siempre el Markdown final con la estructura fija."""
    title = str(sections.get("title") or "Título de la clase").strip()
    title = strip_unwanted_headings(title) or "Título de la clase"
    markdown_parts = [f"# {title}"]

    for key, heading in STUDY_SECTION_DEFINITIONS:
        content = format_section_content(sections.get(key, ""))
        markdown_parts.append(heading)
        markdown_parts.append(content or "No se detectó información suficiente.")

    return "\n\n".join(markdown_parts).strip()


def normalize_transcript_data(
    transcript_data: dict,
    topic_pack: dict | None = None,
) -> dict:
    """Devuelve una copia de transcript_data con el texto normalizado."""
    def normalize_value(value):
        if isinstance(value, str):
            return normalize_terms_with_topic_pack(value, topic_pack=topic_pack)

        if isinstance(value, list):
            return [normalize_value(item) for item in value]

        if isinstance(value, dict):
            return {
                key: normalize_value(item)
                for key, item in value.items()
            }

        return value

    normalized_data = normalize_value(transcript_data)

    return normalized_data


def extract_transcript_text(transcript_data: dict) -> str:
    """Extrae texto suficiente para detectar el tema de la clase."""
    direct_text = transcript_data.get("text")

    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    # Si no existe "text", usamos el JSON completo para cubrir segmentos.
    return json.dumps(transcript_data, ensure_ascii=False)


def build_user_message(
    class_id: str,
    transcript_text: str,
    vision_data: dict | list | None,
    teaching_plan: dict,
    topic_pack: dict | None,
) -> str:
    """Construye el mensaje con los datos de la clase para Ollama."""
    data = {
        "class_id": class_id,
        "transcript_text": transcript_text,
        "vision_data": vision_data,
        "teaching_plan": teaching_plan,
        "topic_pack": topic_pack,
    }

    return (
        "Genera el contenido del material de estudio para esta clase.\n"
        "Devuelve solo JSON valido, sin Markdown y sin bloques de codigo.\n"
        "Usa teaching_plan como guia principal.\n"
        "Usa transcript_text como transcripcion normalizada, no como texto crudo.\n"
        "Si vision_data es null o no aporta informacion, usa principalmente "
        "transcript_text y teaching_plan.\n"
        "El JSON debe usar exactamente estas claves: "
        "title, human_summary, class_goal, seen_in_class, "
        "verified_reinforcement, explanation_from_zero, visual_examples, "
        "code_commands_errors, confusing_parts, prerequisites, micro_challenges, "
        "review_questions, study_plan, transcription_errors.\n\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )


def generate_study_materials(
    class_id: str,
    transcript_data: dict,
    vision_data: dict | list | None,
) -> str:
    """Genera materiales de estudio en Markdown usando Ollama local."""
    transcript_text = extract_transcript_text(transcript_data)
    topic_info = detect_topic(
        transcript_text=transcript_text,
        vision_data=vision_data,
    )
    topic = topic_info.get("topic")
    topic_pack = load_topic_pack(topic)
    normalized_transcript_text = normalize_terms_with_topic_pack(
        transcript_text,
        topic_pack=topic_pack,
    )
    teaching_plan = build_teaching_plan(
        transcript_text=transcript_text,
        vision_data=vision_data,
        topic_info=topic_info,
        topic_pack=topic_pack,
    )
    prompt = (
        f"{load_study_materials_prompt()}\n\n---\n\n"
        f"{build_topic_prompt_context(topic_info, topic_pack)}"
    )
    user_message = build_user_message(
        class_id,
        normalized_transcript_text,
        vision_data,
        teaching_plan,
        topic_pack,
    )

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
        "format": "json",
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

    generated_content = extract_message_content(response_data)

    if not generated_content:
        raise StudyMaterialServiceError(
            "Ollama respondio correctamente, pero no devolvio contenido."
        )

    sections = parse_study_sections(generated_content)
    rendered_markdown = render_study_material_markdown(sections)

    return clean_study_markdown(
        rendered_markdown,
        topic=topic,
        topic_pack=topic_pack,
    )
