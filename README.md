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
