# Classmentor-AI
Asistente multimodal para convertir clases grabadas en apuntes claros, ejercicios y planes de estudio personalizados.

## Ejecutar el backend

Desde la carpeta `backend`, instala las dependencias y arranca FastAPI:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

El backend quedara disponible en:

```text
http://127.0.0.1:8000
```

## Probar el endpoint de salud

Abre en el navegador:

```text
http://127.0.0.1:8000/health
```

La respuesta esperada es:

```json
{
  "status": "ok"
}
```

## Probar la subida de archivos MP4

1. Arranca el backend desde la carpeta `backend`:

```powershell
uvicorn app.main:app --reload
```

2. Abre la documentacion interactiva de FastAPI:

```text
http://127.0.0.1:8000/docs
```

3. Busca el endpoint:

```text
POST /classes/upload
```

4. Pulsa `Try it out`, selecciona un archivo que termine en `.mp4` y pulsa `Execute`.

Si el archivo es valido, recibiras una respuesta parecida a esta:

```json
{
  "class_id": "0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a",
  "original_filename": "mi-clase.mp4",
  "saved_filename": "0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.mp4",
  "saved_path": "backend/uploads/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.mp4",
  "message": "Video uploaded successfully"
}
```

El archivo quedara guardado dentro de:

```text
backend/uploads/
```

Si subes un archivo que no termina en `.mp4`, el backend devolvera un error HTTP 400 con un mensaje claro. Si ocurre un problema al guardar el archivo, devolvera HTTP 500.
