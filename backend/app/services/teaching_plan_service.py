import json


GIT_CORE_CONCEPTS = [
    "git",
    "control de versiones",
    "repositorio",
    "commit",
    "git init",
    "git status",
    "git add",
    "git commit",
    "git diff",
    "git log",
]


def _combined_class_text(transcript_text: str, vision_data) -> str:
    """Une transcripcion y vision para detectar conceptos vistos."""
    combined_text = transcript_text or ""

    if vision_data:
        combined_text += "\n" + json.dumps(vision_data, ensure_ascii=False)

    return combined_text.lower()


def _find_seen_concepts(combined_text: str, concepts: dict) -> list[str]:
    """Devuelve conceptos que aparecen de forma clara en la clase."""
    seen = []

    for concept in concepts:
        if concept.lower() in combined_text:
            seen.append(concept)

    return seen


def _find_transcription_errors(
    transcript_text: str,
    topic_pack: dict | None,
) -> list[dict]:
    """Detecta errores probables que aparecieron en la transcripcion original."""
    if not topic_pack:
        return []

    normalized_text = (transcript_text or "").lower()
    errors = []

    for source, target in topic_pack.get("common_transcription_errors", {}).items():
        if source.lower() in normalized_text:
            errors.append({
                "detected": source,
                "probably_meant": target,
            })

    return errors


def build_teaching_plan(
    transcript_text: str,
    vision_data,
    topic_info: dict,
    topic_pack: dict | None,
) -> dict:
    """Construye un plan pedagogico estructurado sin llamar a Ollama."""
    topic = topic_info.get("topic", "unknown")
    concepts = topic_pack.get("canonical_concepts", {}) if topic_pack else {}
    combined_text = _combined_class_text(transcript_text, vision_data)
    seen_in_class = _find_seen_concepts(combined_text, concepts)

    core_concepts = []
    if topic == "git" and topic_pack:
        for concept in GIT_CORE_CONCEPTS:
            if concept in concepts and (
                concept in seen_in_class
                or concept in ("git", "control de versiones", "repositorio", "commit")
            ):
                core_concepts.append({
                    "concept": concept,
                    "definition": concepts[concept],
                })

    verified_reinforcement = []
    if topic_pack:
        for command, explanation in topic_pack.get("safe_reinforcement", {}).items():
            verified_reinforcement.append({
                "label": "Refuerzo verificado",
                "concept": command,
                "explanation": explanation,
            })

    return {
        "topic": topic,
        "student_level": "beginner",
        "seen_in_class": seen_in_class,
        "probable_transcription_errors": _find_transcription_errors(
            transcript_text,
            topic_pack,
        ),
        "verified_reinforcement": verified_reinforcement,
        "core_concepts": core_concepts,
        "teaching_strategy": {
            "explain_from_zero": True,
            "use_visual_examples": True,
            "use_terminal_examples": True,
            "avoid_robotic_tone": True,
        },
    }
