import json
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = BACKEND_DIR / "app" / "knowledge"


class KnowledgeRetrieverError(RuntimeError):
    """Error leyendo paquetes de conocimiento verificado."""


def load_topic_pack(topic: str) -> dict | None:
    """Carga el paquete de conocimiento para un tema soportado."""
    if topic != "git":
        return None

    topic_pack_path = KNOWLEDGE_DIR / "git_topic_pack.json"

    if not topic_pack_path.exists():
        return None

    try:
        return json.loads(topic_pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise KnowledgeRetrieverError(
            f"El topic pack de {topic} no contiene JSON valido."
        ) from exc
    except OSError as exc:
        raise KnowledgeRetrieverError(
            f"No se pudo leer el topic pack de {topic}."
        ) from exc
