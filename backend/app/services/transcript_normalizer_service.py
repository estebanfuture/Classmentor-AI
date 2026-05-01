import json
import re
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
GIT_TOPIC_PACK_PATH = BACKEND_DIR / "app" / "knowledge" / "git_topic_pack.json"


def load_git_topic_pack() -> dict:
    """Carga el paquete de conocimiento de Git."""
    return json.loads(GIT_TOPIC_PACK_PATH.read_text(encoding="utf-8"))


def normalize_transcript_terms(text: str, topic: str | None = None) -> str:
    """Corrige errores tipicos de transcripcion para el tema detectado."""
    if topic != "git":
        return text

    normalized_text = text
    topic_pack = load_git_topic_pack()
    transcription_errors = topic_pack.get("transcription_errors", {})

    # Ordenamos por longitud para corregir primero frases como "git a punto".
    for source, target in sorted(
        transcription_errors.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        normalized_text = re.sub(
            rf"\b{re.escape(source)}\b",
            target,
            normalized_text,
            flags=re.IGNORECASE,
        )

    return normalized_text
