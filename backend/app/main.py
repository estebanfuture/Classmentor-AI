from fastapi import FastAPI

from app.routes.classes import router as classes_router


app = FastAPI(
    title="ClassMentor AI",
    description="API for processing recorded classes and generating study notes.",
    version="0.1.0",
)

app.include_router(classes_router)


@app.get("/")
def root():
    return {
        "message": "ClassMentor AI backend is running",
        "status": "ok",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }
