import ffmpeg
import asyncio
import os
import re
import static_ffmpeg

# Automatically download and add ffmpeg/ffprobe to the PATH
static_ffmpeg.add_paths()

def get_video_info(file_path):
    """Get video resolution and duration using ffprobe."""
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if not video_stream:
            raise Exception("No video stream found")
        
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        duration = float(probe['format']['duration'])
        has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
        
        return {
            "width": width,
            "height": height,
            "duration": duration,
            "has_audio": has_audio
        }
    except ffmpeg.Error as e:
        print(f"ffmpeg error: {e.stderr.decode('utf8')}")
        raise e

def generate_thumbnail(video_path, output_path):
    """Extract a single frame as a thumbnail."""
    try:
        (
            ffmpeg
            .input(video_path, ss=0)
            .output(output_path, vframes=1, vf='scale=320:-1')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print(f"ffmpeg thumbnail error: {e.stderr.decode('utf8')}")
        raise e

async def export_video(videos, output_path, quality, resolution, master_ratio, format, progress_callback):
    """
    Exports the merged video.
    videos: list of dicts with keys: path, rotate, ratio (Original, 16:9, etc.), fitFill (fit or fill)
    """
    try:
        # Determine global target resolution
        target_w, target_h = 1920, 1080 # Default
        
        if resolution == "1080p":
            target_w, target_h = 1920, 1080
            if master_ratio < 1: # Portrait master
                target_w, target_h = 1080, 1920
        elif resolution == "720p":
            target_w, target_h = 1280, 720
            if master_ratio < 1:
                target_w, target_h = 720, 1280
        else: # original - try to get from first video
            first_info = get_video_info(videos[0]["path"])
            target_w, target_h = first_info["width"], first_info["height"]
            
        # Adjust target based on master_ratio if original is skewed
        if abs(target_w / target_h - master_ratio) > 0.01:
            if master_ratio > 1:
                target_h = int(target_w / master_ratio)
            else:
                target_w = int(target_h * master_ratio)
                
        # Make sure target w/h are even (required for many codecs)
        target_w = target_w - (target_w % 2)
        target_h = target_h - (target_h % 2)

        inputs = []
        video_filters = []
        audio_streams = []

        # Process each input
        for i, v in enumerate(videos):
            input_stream = ffmpeg.input(v["path"])
            inputs.append(input_stream)
            
            v_stream = input_stream.video
            
            # Create a dummy audio stream if the video has no audio
            v_info = get_video_info(v["path"])
            if v_info.get("has_audio"):
                a_stream = input_stream.audio
            else:
                a_stream = ffmpeg.input('anullsrc', f='lavfi', t=v_info["duration"]).audio
            
            # Rotation
            rotate = v.get("rotate", 0)
            if rotate == 90:
                v_stream = v_stream.filter('transpose', 1)
            elif rotate == 180:
                v_stream = v_stream.filter('transpose', 1).filter('transpose', 1)
            elif rotate == -90 or rotate == 270:
                v_stream = v_stream.filter('transpose', 2)

            # Mirror and Flip
            mirror = v.get("mirror", False)
            flip = v.get("flip", False)
            if mirror:
                v_stream = v_stream.filter('hflip')
            if flip:
                v_stream = v_stream.filter('vflip')

            # Aspect Ratio & Fit/Fill
            fit_fill = v.get("fitFill", "fit")
            v_ratio_str = v.get("ratio", "Original")
            
            target_ratio = master_ratio
            if v_ratio_str == "16:9":
                target_ratio = 16/9
            elif v_ratio_str == "9:16":
                target_ratio = 9/16
            elif v_ratio_str == "1:1":
                target_ratio = 1.0
            elif v_ratio_str == "4:5":
                target_ratio = 4/5
            elif v_ratio_str == "2:3":
                target_ratio = 2/3
            elif v_ratio_str == "3:4":
                target_ratio = 3/4
            # If "Original", we stick to the master_ratio bounding box for the final output, 
            # but scale to fit within it.
                
            # To handle fit/fill gracefully into the target target_w x target_h
            if fit_fill == "fill":
                # Scale to fill target, crop the rest
                v_stream = v_stream.filter('scale', f'max({target_w},iw*{target_h}/ih)', f'max({target_h},ih*{target_w}/iw)')
                v_stream = v_stream.filter('crop', target_w, target_h)
            else: # fit
                # Scale to fit target, pad with black
                v_stream = v_stream.filter('scale', f'min({target_w},iw*{target_h}/ih)', f'min({target_h},ih*{target_w}/iw)')
                v_stream = v_stream.filter('pad', target_w, target_h, f'({target_w}-iw)/2', f'({target_h}-ih)/2', color='black')

            v_stream = v_stream.filter('setsar', 1)
            
            # Format to a common pixel format
            v_stream = v_stream.filter('format', 'yuv420p')

            video_filters.append(v_stream)
            audio_streams.append(a_stream)

        # Concat
        joined_streams = []
        for v, a in zip(video_filters, audio_streams):
            joined_streams.append(v)
            joined_streams.append(a)

        concat = ffmpeg.concat(*joined_streams, v=1, a=1)
        out_v = concat.node[0]
        out_a = concat.node[1]
        
        # Output options
        vcodec = 'libx264' if format == 'mp4' else 'prores'
        # Check for GPU (naive fallback to CPU if nvenc fails is harder in pure python-ffmpeg, 
        # so we'll stick to CPU libx264 for broader compatibility, or try nvenc)
        # We will use libx264 as default encoder because it is universally available, much faster than x265, and very reliable.
        # Quality: CRF (0-51), lower is better. Default 23.
        
        output_args = {
            'vcodec': vcodec,
            'acodec': 'aac',
            'crf': quality,
            'preset': 'fast'
        }
        
        if format == 'mp4':
            output_args['pix_fmt'] = 'yuv420p' # Ensure compatibility

        # Since we want progress, we need to run it asynchronously and capture stderr
        cmd = ffmpeg.output(out_v, out_a, output_path, **output_args).overwrite_output().compile()
        
        # Explicitly use the static_ffmpeg executable path to avoid WinError 2
        ffmpeg_exe = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()[0]
        cmd[0] = ffmpeg_exe
        
        import subprocess
        # Run process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        
        duration_total = sum([get_video_info(v["path"])["duration"] for v in videos])
        
        stderr_lines = []
        loop = asyncio.get_event_loop()
        
        # Read stderr for progress
        while True:
            line = await loop.run_in_executor(None, process.stderr.readline)
            if not line:
                break
            
            line_str = line.decode('utf8', errors='ignore')
            stderr_lines.append(line_str)
            # Look for time=00:00:01.23
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line_str)
            if time_match:
                hours = float(time_match.group(1))
                minutes = float(time_match.group(2))
                seconds = float(time_match.group(3))
                current_time = hours * 3600 + minutes * 60 + seconds
                
                progress = min(100, int((current_time / duration_total) * 100)) if duration_total > 0 else 0
                await progress_callback({"status": "processing", "progress": progress})

        await loop.run_in_executor(None, process.wait)
        
        if process.returncode == 0:
            await progress_callback({"status": "completed", "progress": 100})
        else:
            error_log = "".join(stderr_lines[-10:])
            await progress_callback({"status": "error", "message": f"FFmpeg failed:\n{error_log}"})
            
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"Export error: {err_msg}")
        await progress_callback({"status": "error", "message": f"{repr(e)}"})
