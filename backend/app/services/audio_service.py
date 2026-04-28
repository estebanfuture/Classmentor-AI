from pathlib import Path
import subprocess


BACKEND_DIR = Path(__file__).resolve().parents[2]


def resolve_backend_path(path_value: str) -> Path:
    """Convierte rutas tipo backend/uploads/video.mp4 en rutas reales del disco."""
    path = Path(path_value)

    if path.is_absolute() or path.exists():
        return path

    # Si la ruta empieza por backend/, la resolvemos desde la raiz del proyecto.
    if path.parts and path.parts[0] == "backend":
        return BACKEND_DIR.parent / path

    # Si la ruta es relativa, asumimos que vive dentro de backend/.
    return BACKEND_DIR / path


def extract_audio(video_path: str, output_dir: str, class_id: str) -> str:
    """Extrae el audio WAV de un MP4 usando FFmpeg."""
    resolved_video_path = resolve_backend_path(video_path)

    if not resolved_video_path.exists():
        raise FileNotFoundError(f"No existe el video: {video_path}")

    resolved_output_dir = resolve_backend_path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    audio_filename = f"{class_id}.wav"
    resolved_audio_path = resolved_output_dir / audio_filename

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(resolved_video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(resolved_audio_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg no esta instalado o no esta disponible en el PATH del sistema."
        ) from exc
    except subprocess.CalledProcessError as exc:
        error_output = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(f"FFmpeg fallo al extraer el audio: {error_output}") from exc

    return (Path("backend") / "audio" / audio_filename).as_posix()
