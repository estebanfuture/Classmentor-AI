from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile


router = APIRouter(prefix="/classes", tags=["classes"])

# Apunta a backend/uploads aunque uvicorn se ejecute desde otra carpeta.
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"


@router.post("/upload")
def upload_class_video(file: UploadFile = File(...)) -> dict[str, str]:
    """Sube una clase en MP4 y la guarda para procesarla mas adelante."""
    original_filename = file.filename or ""

    # Por ahora solo aceptamos archivos cuyo nombre termina en .mp4.
    if not original_filename.lower().endswith(".mp4"):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos de video con extension .mp4.",
        )

    # Este id sera la referencia estable de la clase en las siguientes fases.
    class_id = str(uuid4())
    saved_filename = f"{class_id}.mp4"
    saved_path = UPLOAD_DIR / saved_filename
    saved_path_response = (Path("backend") / "uploads" / saved_filename).as_posix()

    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        with saved_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el archivo subido.",
        ) from exc

    return {
        "class_id": class_id,
        "original_filename": original_filename,
        "saved_filename": saved_filename,
        "saved_path": saved_path_response,
        "message": "Video uploaded successfully",
    }
