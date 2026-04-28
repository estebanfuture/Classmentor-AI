from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import ClassRecording


router = APIRouter(prefix="/classes", tags=["classes"])

# Apunta a backend/uploads aunque uvicorn se ejecute desde otra carpeta.
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"


def class_recording_to_dict(class_recording: ClassRecording) -> dict[str, str | None]:
    """Convierte un registro de SQLAlchemy en una respuesta JSON sencilla."""
    return {
        "id": class_recording.id,
        "original_filename": class_recording.original_filename,
        "video_path": class_recording.video_path,
        "audio_path": class_recording.audio_path,
        "status": class_recording.status,
        "created_at": class_recording.created_at.isoformat(),
    }


@router.post("/upload")
def upload_class_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, str]:
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

    class_recording = ClassRecording(
        id=class_id,
        original_filename=original_filename,
        video_path=saved_path_response,
        audio_path=None,
        status="uploaded",
    )

    try:
        db.add(class_recording)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el registro de la clase en la base de datos.",
        ) from exc

    return {
        "class_id": class_id,
        "original_filename": original_filename,
        "saved_filename": saved_filename,
        "saved_path": saved_path_response,
        "message": "Video uploaded successfully",
    }


@router.get("")
def list_classes(db: Session = Depends(get_db)) -> list[dict[str, str | None]]:
    """Devuelve todas las clases subidas hasta ahora."""
    class_recordings = (
        db.query(ClassRecording).order_by(ClassRecording.created_at.desc()).all()
    )

    return [
        class_recording_to_dict(class_recording)
        for class_recording in class_recordings
    ]


@router.get("/{class_id}")
def get_class(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    """Devuelve los detalles de una clase concreta."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    return class_recording_to_dict(class_recording)
