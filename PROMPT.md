Here is your complete prompt to build this app:

---

**PROMPT:**

Build a **local web application** for merging 100+ high-resolution 4K HEVC (H.265) videos on **Windows**, using **Python (FastAPI) backend** and **FFmpeg** for video processing.

---

## Tech Stack
- **Backend:** Python + FastAPI + FFmpeg (via `ffmpeg-python` or `subprocess`) + UV (package manger)
- **Frontend:** HTML + CSS + Vanilla JS (or React)
- **Run:** Fully local, open via `localhost` in browser

---

## Core Features

### 1. Video Upload & Drag-and-Drop Order List
- Add multiple videos via an **"Add Video" button** (supports `.mp4`, `.mov`, `.mkv` with HEVC/H.265 codec)
- Display all videos in a **vertical drag-and-drop list** (reorder by dragging)
- Each video card shows: thumbnail, filename, duration, resolution

### 2. Per-Video Edit Controls (on each card)
Clicking a video card opens quick edit options:
- **Rotate:** 90° left, 90° right, 180°
- **Fit / Fill:** Scale video to fit or fill the canvas (based on the ratio of the **first video** in the list as master ratio)
- **Screen Ratio (Video Settings):** Individual ratio override — options: Original, 9:16, 1:1, 16:9, 4:5, 2:3, 3:4

### 3. Global Ratio (Auto-set from First Video)
- When first video is added, **auto-detect its resolution/ratio** and set it as the global canvas size
- All other videos are adjusted (fit/fill) relative to this

### 4. Real-time Browser Preview
- Show a **preview player** in the browser using the video file served from the local Python server
- Allow scrubbing through individual clips before merging
- Show applied transformations (rotation, ratio) visually in preview

### 5. Export Panel
At export time, user chooses:
- **Output format:** HEVC/H.265 (`.mp4`), H.264 (`.mp4`), or ProRes (`.mov`)
- **Quality/CRF:** Slider (lossless → compressed)
- **Resolution:** Keep original 4K, or downscale to 1080p / 720p
- **Output path:** Folder picker (local Windows path)
- Export triggers FFmpeg concat with all transformations applied

---

## FFmpeg Processing Details
- Use **FFmpeg concat demuxer** or `filter_complex` for merging
- Apply per-clip filters: `rotate`, `scale`, `pad`, `setsar` for ratio handling
- Use `-c:v libx265` for HEVC output (GPU-accelerated via `-c:v hevc_nvenc` if NVIDIA GPU detected)
- Audio: copy or re-encode to AAC
- Show **real-time progress bar** in UI using FFmpeg `progress` pipe or WebSocket


---

## Setup Instructions to include in README
1. Install Python 3.10+
2. Install FFmpeg and add to Windows PATH
3. `pip install fastapi uvicorn ffmpeg-python`
4. Run: `uvicorn main:app --reload`
5. Open `http://localhost:8000`

---

Use this prompt in **Cursor, Claude Code, or any AI coding tool** to generate the full project. Ask it to generate: `main.py` (FastAPI), `index.html`, `app.js`, `styles.css`, and `ffmpeg_utils.py` as separate files.