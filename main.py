import os
import shutil
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import WebSocket, WebSocketDisconnect
import tkinter as tk
from tkinter import filedialog
from fastapi.middleware.cors import CORSMiddleware
import json

from ffmpeg_utils import get_video_info, generate_thumbnail, export_video

app = FastAPI(title="Video Merger App")

# Allow CORS if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMP_DIR = BASE_DIR / "temp_uploads"
THUMBNAIL_DIR = BASE_DIR / "temp_thumbnails"

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
THUMBNAIL_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# To keep track of the active websocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        return {"error": "No file uploaded"}
    
    file_path = TEMP_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Get video info using ffprobe
    try:
        info = get_video_info(str(file_path))
    except Exception as e:
        # If ffprobe fails, return default values or error
        return {"error": f"Could not process video: {str(e)}"}
    
    # Generate thumbnail
    thumb_path = THUMBNAIL_DIR / f"{file.filename}.jpg"
    try:
        generate_thumbnail(str(file_path), str(thumb_path))
    except Exception as e:
        print(f"Error generating thumbnail for {file.filename}: {e}")
        pass # It's okay if thumbnail fails, we'll handle it in frontend

    return {
        "filename": file.filename,
        "width": info.get("width", 1920),
        "height": info.get("height", 1080),
        "duration": info.get("duration", 0.0),
        "url": f"/video/{file.filename}",
        "thumbnail": f"/thumbnail/{file.filename}.jpg"
    }

@app.get("/video/{filename}")
async def get_video(filename: str):
    file_path = TEMP_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    return {"error": "File not found"}

@app.get("/thumbnail/{filename}")
async def get_thumbnail(filename: str):
    file_path = THUMBNAIL_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    # Return a default empty response or a placeholder
    return FileResponse(STATIC_DIR / "placeholder.jpg")

@app.get("/pick-folder")
async def pick_folder():
    """Opens a native Windows folder picker dialogue."""
    def _pick():
        root = tk.Tk()
        root.withdraw()
        # Ensure window appears on top
        root.attributes("-topmost", True)
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        root.destroy()
        return folder_path
    
    try:
        # Run in executor to not block the async event loop
        loop = asyncio.get_event_loop()
        folder_path = await loop.run_in_executor(None, _pick)
        return {"path": folder_path}
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/export")
async def export_videos(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    videos = data.get("videos", [])
    output_path = data.get("output_path", "")
    format = data.get("format", "mp4") # mp4 or mov
    quality = data.get("quality", 23)
    resolution = data.get("resolution", "original") # original, 1080, 720
    master_ratio = data.get("master_ratio", 16/9)
    
    if not videos:
        return {"error": "No videos to export"}
    if not output_path:
        return {"error": "No output path selected"}
        
    output_filename = f"merged_output.{format}"
    final_output_path = os.path.join(output_path, output_filename)
    
    # Process each video to gather full paths
    processed_videos = []
    for v in videos:
        v["path"] = str(TEMP_DIR / v["filename"])
        processed_videos.append(v)
        
    async def progress_callback(progress_data):
        await manager.broadcast(json.dumps(progress_data))

    background_tasks.add_task(
        export_video,
        processed_videos,
        final_output_path,
        quality,
        resolution,
        master_ratio,
        format,
        progress_callback
    )

    return {"status": "export_started", "message": "Export has started in the background."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
