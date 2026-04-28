from fastapi import FastAPI

app = FastAPI(
    title="ClassMentor AI",
    description="API for processing recorded classes and generating study notes.",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "ClassMentor AI backend is running",
        "status": "ok",
        "version": "0.1.0"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }
