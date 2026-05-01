import json


GIT_KEYWORDS = [
    "git",
    "commit",
    "commits",
    "repositorio",
    "versiones",
    "control de versiones",
    "git add",
    "git init",
    "git status",
    "git diff",
    "git log",
]


def detect_topic(
    transcript_text: str,
    vision_data: dict | list | None = None,
) -> dict:
    """Detecta el tema principal de la clase de forma simple."""
    combined_text = transcript_text

    if vision_data:
        combined_text += "\n" + json.dumps(vision_data, ensure_ascii=False)

    normalized_text = combined_text.lower()

    if any(keyword in normalized_text for keyword in GIT_KEYWORDS):
        return {
            "topic": "git",
            "confidence": "high",
        }

    return {
        "topic": "unknown",
        "confidence": "low",
    }
