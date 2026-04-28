import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

# Si DATABASE_URL no existe en el entorno, usamos SQLite local por defecto.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./classmentor.db")

# SQLite necesita este ajuste para funcionar bien con FastAPI en desarrollo.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def create_tables() -> None:
    """Crea las tablas de la base de datos si todavia no existen."""
    from app.database import models

    Base.metadata.create_all(bind=engine)


def get_db():
    """Entrega una sesion de base de datos y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
