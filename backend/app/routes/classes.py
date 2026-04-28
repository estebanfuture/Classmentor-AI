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

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # uuid4 evita conflictos si dos usuarios suben archivos con el mismo nombre.
    saved_filename = f"{uuid4()}.mp4"
    saved_path = UPLOAD_DIR / saved_filename

    with saved_path.open("wb") as output_file:
        copyfileobj(file.file, output_file)

    return {
        "status": "uploaded",
        "original_filename": original_filename,
        "saved_filename": saved_filename,
        "saved_path": str(saved_path),
    }
