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


def extract_frames(
    video_path: str,
    output_dir: str,
    class_id: str,
    every_seconds: int = 10,
) -> list[str]:
    """Extrae capturas JPG de un MP4 usando FFmpeg."""
    if every_seconds <= 0:
        raise ValueError("every_seconds debe ser mayor que 0.")

    resolved_video_path = resolve_backend_path(video_path)

    if not resolved_video_path.exists():
        raise FileNotFoundError(f"No existe el video: {video_path}")

    resolved_output_base_dir = resolve_backend_path(output_dir)
    resolved_frames_dir = resolved_output_base_dir / class_id
    resolved_frames_dir.mkdir(parents=True, exist_ok=True)

    # Limpiamos solo capturas generadas previamente para esta clase.
    for frame_path in resolved_frames_dir.glob("frame_*.jpg"):
        if frame_path.is_file():
            frame_path.unlink()

    output_pattern = resolved_frames_dir / "frame_%04d.jpg"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(resolved_video_path),
        "-vf",
        f"fps=1/{every_seconds}",
        str(output_pattern),
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
        raise RuntimeError(f"FFmpeg fallo al extraer frames: {error_output}") from exc

    generated_frames = sorted(resolved_frames_dir.glob("frame_*.jpg"))

    if not generated_frames:
        raise RuntimeError("FFmpeg termino, pero no se genero ningun frame.")

    return [
        (Path("backend") / "frames" / class_id / frame_path.name).as_posix()
        for frame_path in generated_frames
    ]
