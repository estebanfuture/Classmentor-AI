import json
from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import ClassRecording
from app.core.config import (
    MAX_FRAMES_TO_ANALYZE,
    STUDY_PROVIDER,
    VISION_PROVIDER,
    VISION_REQUIRED,
)
from app.services.audio_service import extract_audio
from app.services.study_material_service import (
    StudyMaterialServiceError,
    StudyOllamaConnectionError,
    StudyOllamaModelNotFoundError,
    generate_study_materials,
)
from app.services.transcription_service import transcribe_audio
from app.services.video_service import extract_frames
from app.services.vision_service import (
    InvalidVisionJSONError,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    VisionServiceError,
    analyze_frames,
)


router = APIRouter(prefix="/classes", tags=["classes"])

# Apunta a backend/uploads aunque uvicorn se ejecute desde otra carpeta.
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"
AUDIO_DIR_RESPONSE = Path("backend") / "audio"
FRAMES_DIR_RESPONSE = Path("backend") / "frames"
OUTPUTS_DIR_RESPONSE = Path("backend") / "outputs"


def resolve_backend_response_path(path_value: str | Path) -> Path:
    """Convierte rutas tipo backend/outputs/x.json en rutas reales del disco."""
    path = Path(path_value)

    if path.is_absolute() or path.exists():
        return path

    if path.parts and path.parts[0] == "backend":
        return BACKEND_DIR.parent / path

    return BACKEND_DIR / path


def update_class_status(
    db: Session,
    class_recording: ClassRecording,
    status: str,
) -> None:
    """Actualiza y guarda el estado de una clase."""
    class_recording.status = status

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(
            "No se pudo actualizar el estado de la clase en la base de datos."
        ) from exc


def fail_process_all(
    db: Session,
    class_recording: ClassRecording,
    failed_step: str,
    error_message: str,
    warnings: list[dict[str, str]] | None = None,
) -> dict:
    """Marca una clase como fallida y devuelve una respuesta clara."""
    class_recording.status = "failed"

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    return {
        "class_id": class_recording.id,
        "status": "failed",
        "failed_step": failed_step,
        "error_message": error_message,
        "warnings": warnings or [],
    }


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


@router.post("/{class_id}/analyze-frames")
def analyze_class_frames(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    """Analiza capturas de una clase usando Ollama Vision local."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    if VISION_PROVIDER.lower().strip() != "ollama":
        raise HTTPException(
            status_code=500,
            detail="VISION_PROVIDER debe ser 'ollama' en esta fase.",
        )

    resolved_frames_dir = BACKEND_DIR.parent / FRAMES_DIR_RESPONSE / class_id
    frame_files = sorted(resolved_frames_dir.glob("frame_*.jpg"))

    if not frame_files:
        raise HTTPException(
            status_code=400,
            detail="No hay capturas para esta clase. Primero ejecuta extract-frames.",
        )

    frame_paths = [
        (FRAMES_DIR_RESPONSE / class_id / frame_file.name).as_posix()
        for frame_file in frame_files
    ]

    try:
        vision_results = analyze_frames(
            frame_paths=frame_paths,
            max_frames=MAX_FRAMES_TO_ANALYZE,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except InvalidVisionJSONError as exc:
        raw_response_filename = f"{class_id}_vision_raw_response.txt"
        raw_response_path = OUTPUTS_DIR_RESPONSE / raw_response_filename
        resolved_raw_response_path = BACKEND_DIR.parent / raw_response_path

        try:
            resolved_raw_response_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_raw_response_path.write_text(exc.raw_response, encoding="utf-8")
            detail = (
                f"{exc} Respuesta cruda guardada en "
                f"{raw_response_path.as_posix()}."
            )
        except OSError:
            detail = f"{exc} Ademas, no se pudo guardar la respuesta cruda."

        raise HTTPException(status_code=500, detail=detail) from exc
    except VisionServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    vision_filename = f"{class_id}_vision.json"
    vision_path = OUTPUTS_DIR_RESPONSE / vision_filename
    resolved_vision_path = BACKEND_DIR.parent / vision_path

    vision_data = {
        "class_id": class_id,
        "frames_analyzed": len(vision_results),
        "max_frames_to_analyze": MAX_FRAMES_TO_ANALYZE,
        "results": vision_results,
    }

    try:
        resolved_vision_path.parent.mkdir(parents=True, exist_ok=True)

        with resolved_vision_path.open("w", encoding="utf-8") as output_file:
            json.dump(vision_data, output_file, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el archivo JSON de analisis visual.",
        ) from exc

    class_recording.status = "vision_analyzed"

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
        "frames_analyzed": len(vision_results),
        "vision_path": vision_path.as_posix(),
        "status": class_recording.status,
        "message": "Frames analyzed successfully",
    }


@router.post("/{class_id}/generate-study-materials")
def generate_class_study_materials(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Genera materiales de estudio Markdown desde transcripcion y vision."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    if STUDY_PROVIDER.lower().strip() != "ollama":
        raise HTTPException(
            status_code=500,
            detail="STUDY_PROVIDER debe ser 'ollama' en esta fase.",
        )

    transcript_filename = f"{class_id}_transcript.json"
    transcript_path = OUTPUTS_DIR_RESPONSE / transcript_filename
    resolved_transcript_path = BACKEND_DIR.parent / transcript_path

    if not resolved_transcript_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No existe la transcripcion. Primero ejecuta transcribe.",
        )

    try:
        transcript_data = json.loads(
            resolved_transcript_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo leer el JSON de transcripcion.",
        ) from exc

    vision_filename = f"{class_id}_vision.json"
    vision_path = OUTPUTS_DIR_RESPONSE / vision_filename
    resolved_vision_path = BACKEND_DIR.parent / vision_path
    vision_data = None

    if resolved_vision_path.exists():
        try:
            vision_data = json.loads(resolved_vision_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=500,
                detail="No se pudo leer el JSON de analisis visual.",
            ) from exc

    transcript_text = str(transcript_data.get("text", "")).strip()
    warning = None

    if not transcript_text:
        warning = (
            "Advertencia: la transcripcion esta vacia. "
            "Se genero un material minimo con la informacion disponible."
        )

    try:
        markdown = generate_study_materials(
            class_id=class_id,
            transcript_data=transcript_data,
            vision_data=vision_data,
        )
    except StudyOllamaModelNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StudyOllamaConnectionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StudyMaterialServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    study_material_filename = f"{class_id}_study_material.md"
    study_material_path = OUTPUTS_DIR_RESPONSE / study_material_filename
    resolved_study_material_path = BACKEND_DIR.parent / study_material_path

    try:
        resolved_study_material_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_study_material_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el archivo Markdown de materiales de estudio.",
        ) from exc

    class_recording.status = "study_materials_generated"

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo actualizar el registro de la clase en la base de datos.",
        ) from exc

    message = "Study materials generated successfully"

    if warning:
        message = f"{message}. {warning}"

    return {
        "class_id": class_recording.id,
        "study_material_path": study_material_path.as_posix(),
        "status": class_recording.status,
        "message": message,
    }


@router.post("/{class_id}/process-all")
def process_all_class(
    class_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Ejecuta todo el pipeline local de una clase ya subida."""
    class_recording = db.get(ClassRecording, class_id)

    if class_recording is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una clase con ese class_id.",
        )

    resolved_video_path = resolve_backend_response_path(class_recording.video_path)

    if not resolved_video_path.exists():
        return fail_process_all(
            db=db,
            class_recording=class_recording,
            failed_step="video",
            error_message=f"No existe el video: {class_recording.video_path}",
        )

    steps = {
        "audio": "pending",
        "frames": "pending",
        "transcription": "pending",
        "vision": "pending",
        "study_materials": "pending",
    }
    outputs = {
        "audio_path": None,
        "frames_dir": None,
        "transcript_path": None,
        "vision_path": None,
        "study_material_path": None,
    }
    warnings = []

    try:
        update_class_status(db, class_recording, "processing_audio")
        audio_path = extract_audio(
            video_path=class_recording.video_path,
            output_dir=str(AUDIO_DIR_RESPONSE),
            class_id=class_id,
        )
        class_recording.audio_path = audio_path
        update_class_status(db, class_recording, "audio_extracted")
        steps["audio"] = "completed"
        outputs["audio_path"] = audio_path
    except (FileNotFoundError, RuntimeError) as exc:
        return fail_process_all(db, class_recording, "audio", str(exc))

    try:
        update_class_status(db, class_recording, "extracting_frames")
        frame_paths = extract_frames(
            video_path=class_recording.video_path,
            output_dir=str(FRAMES_DIR_RESPONSE),
            class_id=class_id,
        )
        update_class_status(db, class_recording, "frames_extracted")
        steps["frames"] = "completed"
        outputs["frames_dir"] = (FRAMES_DIR_RESPONSE / class_id).as_posix()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return fail_process_all(db, class_recording, "frames", str(exc))

    try:
        update_class_status(db, class_recording, "transcribing")
        transcription = transcribe_audio(audio_path)

        transcript_path = OUTPUTS_DIR_RESPONSE / f"{class_id}_transcript.json"
        resolved_transcript_path = resolve_backend_response_path(transcript_path)
        transcript_data = {
            "class_id": class_id,
            "audio_path": audio_path,
            "text": transcription["text"],
            "raw_response": transcription["raw_response"],
        }

        resolved_transcript_path.parent.mkdir(parents=True, exist_ok=True)

        with resolved_transcript_path.open("w", encoding="utf-8") as output_file:
            json.dump(transcript_data, output_file, ensure_ascii=False, indent=2)

        update_class_status(db, class_recording, "transcribed")
        steps["transcription"] = "completed"
        outputs["transcript_path"] = transcript_path.as_posix()
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        return fail_process_all(db, class_recording, "transcription", str(exc))

    vision_path = OUTPUTS_DIR_RESPONSE / f"{class_id}_vision.json"
    resolved_vision_path = resolve_backend_response_path(vision_path)
    vision_data = None

    try:
        if resolved_vision_path.exists():
            vision_data = json.loads(resolved_vision_path.read_text(encoding="utf-8"))
            steps["vision"] = "reused"
            outputs["vision_path"] = vision_path.as_posix()
        else:
            if VISION_PROVIDER.lower().strip() != "ollama":
                raise RuntimeError("VISION_PROVIDER debe ser 'ollama' en esta fase.")

            update_class_status(db, class_recording, "analyzing_frames")
            vision_results = analyze_frames(
                frame_paths=frame_paths,
                max_frames=MAX_FRAMES_TO_ANALYZE,
            )

            vision_data = {
                "class_id": class_id,
                "frames_analyzed": len(vision_results),
                "max_frames_to_analyze": MAX_FRAMES_TO_ANALYZE,
                "results": vision_results,
            }

            resolved_vision_path.parent.mkdir(parents=True, exist_ok=True)

            with resolved_vision_path.open("w", encoding="utf-8") as output_file:
                json.dump(vision_data, output_file, ensure_ascii=False, indent=2)

            update_class_status(db, class_recording, "vision_analyzed")
            steps["vision"] = "completed"
            outputs["vision_path"] = vision_path.as_posix()
    except InvalidVisionJSONError as exc:
        raw_response_path = OUTPUTS_DIR_RESPONSE / f"{class_id}_vision_raw_response.txt"
        resolved_raw_response_path = resolve_backend_response_path(raw_response_path)

        try:
            resolved_raw_response_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_raw_response_path.write_text(exc.raw_response, encoding="utf-8")
            error_message = (
                f"{exc} Respuesta cruda guardada en "
                f"{raw_response_path.as_posix()}."
            )
        except OSError:
            error_message = f"{exc} No se pudo guardar la respuesta cruda."

        if VISION_REQUIRED:
            return fail_process_all(db, class_recording, "vision", error_message)

        warnings.append(
            {
                "step": "vision",
                "message": error_message,
            }
        )
        steps["vision"] = "warning"
        vision_data = None
    except (
        FileNotFoundError,
        OllamaModelNotFoundError,
        OllamaConnectionError,
        VisionServiceError,
        RuntimeError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        if VISION_REQUIRED:
            return fail_process_all(db, class_recording, "vision", str(exc))

        warnings.append(
            {
                "step": "vision",
                "message": str(exc),
            }
        )
        steps["vision"] = "warning"
        vision_data = None

    try:
        if STUDY_PROVIDER.lower().strip() != "ollama":
            raise RuntimeError("STUDY_PROVIDER debe ser 'ollama' en esta fase.")

        update_class_status(db, class_recording, "generating_study_materials")
        markdown = generate_study_materials(
            class_id=class_id,
            transcript_data=transcript_data,
            vision_data=vision_data,
        )

        study_material_path = (
            OUTPUTS_DIR_RESPONSE / f"{class_id}_study_material.md"
        )
        resolved_study_material_path = resolve_backend_response_path(
            study_material_path
        )

        resolved_study_material_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_study_material_path.write_text(markdown, encoding="utf-8")

        update_class_status(db, class_recording, "study_materials_generated")
        steps["study_materials"] = "completed"
        outputs["study_material_path"] = study_material_path.as_posix()
    except (
        StudyOllamaModelNotFoundError,
        StudyOllamaConnectionError,
        StudyMaterialServiceError,
        RuntimeError,
        OSError,
    ) as exc:
        return fail_process_all(
            db,
            class_recording,
            "study_materials",
            str(exc),
            warnings=warnings,
        )

    final_status = "completed_with_warnings" if warnings else "completed"

    try:
        update_class_status(db, class_recording, final_status)
    except RuntimeError as exc:
        return fail_process_all(
            db,
            class_recording,
            "completed",
            str(exc),
            warnings=warnings,
        )

    return {
        "class_id": class_recording.id,
        "status": final_status,
        "steps": steps,
        "outputs": outputs,
        "warnings": warnings,
        "message": (
            "Class processed successfully with warnings"
            if warnings
            else "Class processed successfully"
        ),
    }
