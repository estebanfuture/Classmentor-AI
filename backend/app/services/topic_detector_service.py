import json


GIT_KEYWORDS = [
    "git",
    "commit",
    "commits",
    "repositorio",
    "versiones",
    "control de versiones",
    "versionamiento",
    "git add",
    "git init",
    "git status",
    "git diff",
    "git log",
]


def detect_topic(
    transcript_text: str,
    vision_data=None,
) -> dict:
    """Detecta el tema principal de la clase de forma simple y explicable."""
    combined_text = transcript_text or ""

    if vision_data:
        combined_text += "\n" + json.dumps(vision_data, ensure_ascii=False)

    normalized_text = combined_text.lower()
    detected_keywords = [
        keyword
        for keyword in GIT_KEYWORDS
        if keyword in normalized_text
    ]

    if detected_keywords:
        return {
            "topic": "git",
            "confidence": "high",
            "detected_keywords": detected_keywords,
        }

    return {
        "topic": "unknown",
        "confidence": "low",
        "detected_keywords": [],
    }
