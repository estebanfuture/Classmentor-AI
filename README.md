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

## Requisito para extraer audio y capturas

Para usar la extraccion de audio o capturas, FFmpeg debe estar instalado en Windows y disponible en el `PATH`.

Puedes comprobarlo desde una terminal con:

```powershell
ffmpeg -version
```

Si el comando muestra informacion de version, FastAPI podra usar FFmpeg desde los endpoints de extraccion.

## Base de datos SQLite

ClassMentor AI usa SQLAlchemy para guardar un registro basico de cada clase subida.

Si no configuras nada, la app crea automaticamente una base de datos SQLite en la carpeta `backend`:

```text
backend/classmentor.db
```

La URL por defecto es:

```text
sqlite:///./classmentor.db
```

Si mas adelante quieres usar otra ruta de base de datos, puedes definir `DATABASE_URL` en un archivo `.env` dentro de `backend`:

```text
DATABASE_URL=sqlite:///./classmentor.db
```

Las tablas se crean automaticamente al arrancar el servidor si todavia no existen.

## Configurar OpenAI para transcripcion

La transcripcion usa la API de OpenAI. FastAPI puede arrancar aunque no exista `OPENAI_API_KEY`, pero el endpoint de transcripcion devolvera un error claro si intentas usarlo sin clave.

En la carpeta `backend`, crea un archivo `.env`:

```powershell
copy .env.example .env
```

Edita `backend/.env` y configura:

```text
OPENAI_API_KEY=tu_clave_de_openai
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

El archivo `.env` no debe subirse a GitHub. Ya esta incluido en `.gitignore`.

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

Ademas, la subida crea un registro en SQLite con:

```text
id = class_id
original_filename = nombre original del archivo
video_path = backend/uploads/{class_id}.mp4
audio_path = null
status = uploaded
created_at = fecha de creacion
```

## Probar la lista de clases

Despues de subir al menos un MP4, abre Swagger:

```text
http://127.0.0.1:8000/docs
```

Busca y ejecuta:

```text
GET /classes
```

La respuesta sera una lista con las clases subidas.

## Probar el detalle de una clase

Copia el `class_id` devuelto por `POST /classes/upload` o el `id` devuelto por `GET /classes`.

En Swagger, busca:

```text
GET /classes/{class_id}
```

Pega ese identificador y pulsa `Execute`.

Si existe, veras los detalles de esa clase. Si no existe, el backend devolvera HTTP 404 con un mensaje claro.

## Probar la extraccion de audio

Primero sube un MP4 con:

```text
POST /classes/upload
```

Antes de extraer audio, el detalle de la clase tendra:

```json
{
  "audio_path": null,
  "status": "uploaded"
}
```

Despues, copia el `class_id` y ejecuta en Swagger:

```text
POST /classes/{class_id}/extract-audio
```

Si todo va bien, FFmpeg generara un archivo WAV en:

```text
backend/audio/{class_id}.wav
```

La respuesta sera parecida a esta:

```json
{
  "class_id": "0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a",
  "video_path": "backend/uploads/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.mp4",
  "audio_path": "backend/audio/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.wav",
  "status": "audio_extracted",
  "message": "Audio extracted successfully"
}
```

Si vuelves a ejecutar:

```text
GET /classes/{class_id}
```

veras `audio_path` con la ruta del WAV y `status` como `audio_extracted`.

## Probar la extraccion de capturas

Primero sube un MP4 con:

```text
POST /classes/upload
```

Despues, copia el `class_id` y ejecuta en Swagger:

```text
POST /classes/{class_id}/extract-frames
```

Por defecto, FFmpeg extraera una captura cada 10 segundos y guardara las imagenes en:

```text
backend/frames/{class_id}/
```

Los archivos tendran este formato:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
```

Si ya existen capturas anteriores para esa clase, el backend eliminara solo los archivos `frame_*.jpg` dentro de `backend/frames/{class_id}/` antes de generar las nuevas.

La respuesta sera parecida a esta:

```json
{
  "class_id": "0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a",
  "video_path": "backend/uploads/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.mp4",
  "frames_dir": "backend/frames/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a",
  "total_frames": 3,
  "frame_paths": [
    "backend/frames/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a/frame_0001.jpg",
    "backend/frames/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a/frame_0002.jpg",
    "backend/frames/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a/frame_0003.jpg"
  ],
  "status": "frames_extracted",
  "message": "Frames extracted successfully"
}
```

Si vuelves a ejecutar:

```text
GET /classes/{class_id}
```

veras `status` como `frames_extracted`.

## Probar la transcripcion de audio

Primero sube un MP4:

```text
POST /classes/upload
```

Despues extrae el audio:

```text
POST /classes/{class_id}/extract-audio
```

Cuando `GET /classes/{class_id}` muestre `audio_path` con una ruta valida, ejecuta en Swagger:

```text
POST /classes/{class_id}/transcribe
```

Si falta `OPENAI_API_KEY`, el backend devolvera un error claro sin romper `/health` ni el arranque del servidor.

Si la clave existe y el audio es valido, se generara:

```text
backend/outputs/{class_id}_transcript.json
```

La respuesta sera parecida a esta:

```json
{
  "class_id": "0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a",
  "audio_path": "backend/audio/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a.wav",
  "transcript_path": "backend/outputs/0d6b5d4a-9ef8-4a5e-8f6d-93a9e3d41b4a_transcript.json",
  "text_preview": "Primeros 500 caracteres de la transcripcion...",
  "status": "transcribed",
  "message": "Audio transcribed successfully"
}
```

Si vuelves a ejecutar:

```text
GET /classes/{class_id}
```

veras `status` como `transcribed`.
