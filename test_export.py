import asyncio
import json
from ffmpeg_utils import export_video
from pathlib import Path

async def test_export():
    # Provide a dummy video or find an existing one
    import glob
    videos = glob.glob("temp_uploads/*.mp4")
    if not videos:
        # Create a dummy video
        import static_ffmpeg
        ffmpeg_exe = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()[0]
        import subprocess
        subprocess.run([ffmpeg_exe, "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=2", "-c:v", "libx264", "temp_uploads/dummy.mp4", "-y"])
        videos = ["temp_uploads/dummy.mp4"]
        
    v_path = Path(videos[0]).resolve()
    
    videos_payload = [{
        "path": str(v_path),
        "rotate": 0,
        "ratio": "Original",
        "fitFill": "fit",
        "mirror": False,
        "flip": False
    }]
    
    output_path = str((Path("temp_uploads") / "out.mp4").resolve())
    
    async def progress(msg):
        print("PROGRESS:", msg)
        
    print("Starting export...")
    await export_video(videos_payload, output_path, 23, "original", 1.777, "mp4", progress)
    print("Done")

asyncio.run(test_export())
