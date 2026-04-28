from datetime import datetime

from sqlalchemy import Column, DateTime, String

from app.database.db import Base


class ClassRecording(Base):
    """Registro basico de una clase subida por el usuario."""

    __tablename__ = "class_recordings"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String, nullable=False)
    video_path = Column(String, nullable=False)
    audio_path = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
