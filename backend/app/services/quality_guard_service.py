import re


def split_markdown_code_blocks(markdown: str) -> list[tuple[str, str]]:
    """Separa texto normal y bloques de codigo para no romper ejemplos."""
    parts = []
    current_lines = []
    current_kind = "text"

    for line in markdown.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            if current_lines:
                parts.append((current_kind, "".join(current_lines)))
                current_lines = []

            current_lines.append(line)
            current_kind = "code" if current_kind == "text" else "text"
            continue

        current_lines.append(line)

    if current_lines:
        parts.append((current_kind, "".join(current_lines)))

    return parts


def clean_git_text(text: str) -> str:
    """Corrige explicaciones frecuentes mal generadas sobre Git."""
    replacements = [
        (
            r"`?git`?:\s*sirve para iniciar un repositorio",
            "`git init`: sirve para iniciar un repositorio Git.",
        ),
        (
            r"`?git`?\s+sirve para iniciar un repositorio",
            "`git init` sirve para iniciar un repositorio Git.",
        ),
        (
            r"`?git init`?:\s*sirve para ver los cambios en los archivos",
            "`git status`: sirve para ver el estado actual del proyecto.",
        ),
        (
            r"`?git init`?\s+sirve para ver cambios",
            "`git status` sirve para ver el estado actual del proyecto.",
        ),
        (
            r"`?git init`?:\s*sirve para ver cambios",
            "`git status`: sirve para ver el estado actual del proyecto.",
        ),
        (
            r"`?git init`?:\s*sirve para ver el estado",
            "`git status`: sirve para ver el estado actual del proyecto.",
        ),
        (
            r"\bgit diff prepara archivos\b",
            "git diff muestra las diferencias entre los cambios actuales y la ultima version guardada.",
        ),
        (
            r"\bgit add agrega archivos al repositorio\b",
            "git add prepara archivos para incluirlos en el proximo commit.",
        ),
        (
            r"\bprepara archivos para ser comittados\b",
            "prepara archivos para incluirlos en el proximo commit.",
        ),
        (r"\bcommands basicos\b", "comandos basicos"),
        (r"\bcommands básicos\b", "comandos básicos"),
        (r"\bmensaje de comité\b", "mensaje de commit"),
        (r"\bhacer un comité\b", "hacer un commit"),
        (r"\bcrear un comité\b", "crear un commit"),
        (r"\bcomités\b", "commits"),
        (r"\bcomité\b", "commit"),
        (r"\bcomits\b", "commits"),
        (r"\bcomit\b", "commit"),
    ]

    cleaned_text = text

    for source, target in replacements:
        cleaned_text = re.sub(source, target, cleaned_text, flags=re.IGNORECASE)

    return re.sub(
        r"git diff[^.\n]*(prepara|preparar|preparan|preparando)[^.\n]*(archivos|cambios)[^.\n]*(\.|\n|$)",
        "git diff muestra las diferencias entre los cambios actuales y la ultima version guardada.\n",
        cleaned_text,
        flags=re.IGNORECASE,
    )


def remove_internal_sections(markdown: str) -> str:
    """Quita secciones internas que no deben mostrarse al alumno."""
    internal_markers = (
        "vision data",
        "reglas pedagogicas",
        "reglas pedagógicas",
        "instrucciones internas",
        "instrucciones para el modelo",
        "prompt interno",
    )
    cleaned_lines = []
    skipping_internal_section = False

    for line in markdown.splitlines():
        stripped_line = line.strip()
        normalized_heading = stripped_line.lstrip("#").strip().lower().rstrip(":")
        is_heading = stripped_line.startswith("#")

        if any(marker in normalized_heading for marker in internal_markers):
            skipping_internal_section = is_heading
            continue

        if skipping_internal_section and is_heading:
            skipping_internal_section = False

        if skipping_internal_section:
            continue

        if any(marker in stripped_line.lower() for marker in internal_markers):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def remove_incomplete_transcription_notes(markdown: str) -> str:
    """Elimina notas incompletas en Posibles errores de transcripcion."""
    cleaned_lines = []
    inside_transcription_notes = False

    for line in markdown.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("## "):
            inside_transcription_notes = (
                "posibles errores de transcrip" in stripped_line.lower()
            )

        if inside_transcription_notes:
            normalized_line = stripped_line.rstrip(".:;,- ")

            if (
                normalized_line.endswith("Si aparece una frase parecida a")
                or normalized_line.endswith("->")
                or normalized_line.endswith("probablemente")
                or normalized_line.endswith("puede ser")
                or normalized_line in ("-", "- ")
            ):
                continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def remove_unsupported_git_lines(markdown: str) -> str:
    """Elimina temas claramente ajenos cuando la clase detectada es Git."""
    unsupported_terms = [
        "pandas",
        "os módulo",
        "os modulo",
        "biblioteca pandas",
        "importar datos",
    ]
    cleaned_parts = []

    for kind, content in split_markdown_code_blocks(markdown):
        if kind == "code":
            cleaned_parts.append(content)
            continue

        kept_lines = []

        for line in content.splitlines(keepends=True):
            normalized_line = line.lower()

            if any(term in normalized_line for term in unsupported_terms):
                continue

            kept_lines.append(line)

        cleaned_parts.append("".join(kept_lines))

    return "".join(cleaned_parts).strip()


def apply_quality_guard(
    markdown: str,
    topic: str | None = None,
    topic_pack: dict | None = None,
) -> str:
    """Aplica controles de calidad pedagogica al Markdown final."""
    cleaned_markdown = remove_internal_sections(markdown)
    cleaned_markdown = remove_incomplete_transcription_notes(cleaned_markdown)

    cleaned_parts = []

    for kind, content in split_markdown_code_blocks(cleaned_markdown):
        if kind == "code":
            cleaned_parts.append(content)
        elif topic == "git":
            cleaned_parts.append(clean_git_text(content))
        else:
            cleaned_parts.append(content)

    cleaned_markdown = "".join(cleaned_parts).strip()

    if topic == "git":
        cleaned_markdown = remove_unsupported_git_lines(cleaned_markdown)

    return cleaned_markdown.strip()
