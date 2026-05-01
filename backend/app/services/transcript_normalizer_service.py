import re


def normalize_transcript_terms(
    text: str,
    topic_pack: dict | None = None,
) -> str:
    """Corrige errores tipicos de transcripcion usando conocimiento verificado."""
    if not text or not topic_pack:
        return text

    transcription_errors = topic_pack.get("common_transcription_errors", {})
    normalized_text = text

    # Ordenamos por longitud para corregir primero frases como "git commit guion m".
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
