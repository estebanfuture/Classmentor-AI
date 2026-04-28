import json
from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import ClassRecording
from app.services.audio_service import extract_audio
from app.services.transcription_service import transcribe_audio
from app.services.video_service import extract_frames


router = APIRouter(prefix="/classes", tags=["classes"])

# Apunta a backend/uploads aunque uvicorn se ejecute desde otra carpeta.
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"
AUDIO_DIR_RESPONSE = Path("backend") / "audio"
FRAMES_DIR_RESPONSE = Path("backend") / "frames"
OUTPUTS_DIR_RESPONSE = Path("backend") / "outputs"


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


@router.post("/{class_id}/extract-audio")
def extract_class_audio(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Extrae el audio WAV de una clase ya subida."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    try:
        audio_path = extract_audio(
            video_path=class_recording.video_path,
            output_dir=str(AUDIO_DIR_RESPONSE),
            class_id=class_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    class_recording.audio_path = audio_path
    class_recording.status = "audio_extracted"

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo actualizar el registro de la clase en la base de datos.",
        ) from exc

    return {
        "class_id": class_recording.id,
        "video_path": class_recording.video_path,
        "audio_path": class_recording.audio_path,
        "status": class_recording.status,
        "message": "Audio extracted successfully",
    }


@router.post("/{class_id}/extract-frames")
def extract_class_frames(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str | int | list[str]]:
    """Extrae capturas JPG de una clase ya subida."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    try:
        frame_paths = extract_frames(
            video_path=class_recording.video_path,
            output_dir=str(FRAMES_DIR_RESPONSE),
            class_id=class_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    class_recording.status = "frames_extracted"

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo actualizar el registro de la clase en la base de datos.",
        ) from exc

    frames_dir = (FRAMES_DIR_RESPONSE / class_id).as_posix()

    return {
        "class_id": class_recording.id,
        "video_path": class_recording.video_path,
        "frames_dir": frames_dir,
        "total_frames": len(frame_paths),
        "frame_paths": frame_paths,
        "status": class_recording.status,
        "message": "Frames extracted successfully",
    }


@router.post("/{class_id}/transcribe")
def transcribe_class_audio(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Transcribe el audio extraido de una clase."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    if not class_recording.audio_path:
        raise HTTPException(
            status_code=400,
            detail="Primero debes extraer el audio de esta clase.",
        )

    try:
        transcription = transcribe_audio(class_recording.audio_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    transcript_filename = f"{class_id}_transcript.json"
    transcript_path = OUTPUTS_DIR_RESPONSE / transcript_filename
    resolved_transcript_path = BACKEND_DIR.parent / transcript_path

    transcript_data = {
        "class_id": class_id,
        "audio_path": class_recording.audio_path,
        "text": transcription["text"],
        "raw_response": transcription["raw_response"],
    }

    try:
        resolved_transcript_path.parent.mkdir(parents=True, exist_ok=True)

        with resolved_transcript_path.open("w", encoding="utf-8") as output_file:
            json.dump(transcript_data, output_file, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el archivo de transcripcion.",
        ) from exc

    class_recording.status = "transcribed"

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo actualizar el registro de la clase en la base de datos.",
        ) from exc

    return {
        "class_id": class_recording.id,
        "audio_path": class_recording.audio_path,
        "transcript_path": transcript_path.as_posix(),
        "text_preview": transcription["text"][:500],
        "status": class_recording.status,
        "message": "Audio transcribed successfully",
    }
