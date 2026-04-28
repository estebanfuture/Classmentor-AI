from fastapi import FastAPI

app = FastAPI(
    title="ClassMentor AI",
    description="API para procesar clases grabadas y generar apuntes inteligentes.",
    version="0.1.0"
)


@app.get("/")
def health_check():
    return {
        "message": "ClassMentor AI backend is running",
        "status": "ok",
        "version": "0.1.0"
    }
