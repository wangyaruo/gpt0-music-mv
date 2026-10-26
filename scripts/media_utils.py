import os
import re
import shutil
import subprocess
from pathlib import Path


def ffmpeg_path(explicit=None):
  candidates = [explicit, os.environ.get("FFMPEG_BIN"), shutil.which("ffmpeg"), str(Path.home()/".local/bin/ffmpeg")]
  for value in candidates:
    if value and Path(value).is_file():
      return str(Path(value).resolve())
  raise ValueError("找不到 FFmpeg；安装后放入 PATH，或指定 --ffmpeg /path/to/ffmpeg。")


def probe(path, ffmpeg):
  path = Path(path)
  if not path.is_file():
    raise ValueError("媒体文件不存在：" + str(path))
  process = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=30)
  text = process.stderr
  duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
  if not duration:
    raise ValueError("无法读取媒体时长：" + text[-1000:])
  video = next((line for line in text.splitlines() if "Video:" in line), "")
  audio = next((line for line in text.splitlines() if "Audio:" in line), "")
  dimensions = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video)
  fps = re.search(r"([\d.]+) fps", video)
  hours, minutes, seconds = map(float, duration.groups())
  return {"duration": hours*3600+minutes*60+seconds,
          "width": int(dimensions[1]) if dimensions else None,
          "height": int(dimensions[2]) if dimensions else None,
          "fps": float(fps[1]) if fps else None, "has_audio": bool(audio),
          "video_stream": video.strip(), "audio_stream": audio.strip(), "raw_metadata": text}
