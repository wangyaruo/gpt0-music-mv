#!/usr/bin/env python3
"""Extract timed frames, a contact sheet, scene candidates and audio signal measurements."""
import argparse
import array
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path
from PIL import Image, ImageDraw
from media_utils import ffmpeg_path, probe


def audio_stats(path):
  with wave.open(str(path)) as reader:
    rate = reader.getframerate()
    samples = array.array("h",reader.readframes(reader.getnframes()))
    if sys.byteorder != "little":
      samples.byteswap()
  if not samples:
    return {"sample_rate":rate,"duration":0,"tempo_candidates":[]}
  rms = math.sqrt(sum((value/32768)**2 for value in samples)/len(samples))
  peak = max(abs(value) for value in samples)/32768
  result = {"sample_rate":rate,"duration":len(samples)/rate,"rms_dbfs":20*math.log10(max(rms,1e-12)),
            "peak_dbfs":20*math.log10(max(peak,1e-12)),"measurement":"decoded mono dBFS, not LUFS",
            "tempo_candidates":[],"tempo_status":"unavailable_without_optional_numpy"}
  try:
    import numpy as np
  except ImportError:
    return result
  values = np.asarray(samples,dtype=np.float32)/32768
  nfft,hop = 1024,256
  window = np.hanning(nfft)
  previous = np.zeros(nfft//2+1)
  flux = []
  for index in range(0,len(values)-nfft,hop):
    spectrum = np.abs(np.fft.rfft(values[index:index+nfft]*window))
    flux.append(float(np.maximum(spectrum-previous,0).sum()))
    previous = spectrum
  if len(flux) < 150:
    result["tempo_status"] = "audio_too_short"
    return result
  flux = np.asarray(flux)
  flux = np.maximum(0,flux-flux.mean())
  envelope_rate = rate/hop
  candidates = []
  for lag in range(int(envelope_rate*60/180),int(envelope_rate*60/65)+1):
    score = float(np.dot(flux[:-lag],flux[lag:])/(np.linalg.norm(flux[:-lag])*np.linalg.norm(flux[lag:])+1e-9))
    candidates.append({"bpm":round(60*envelope_rate/lag,2),"autocorrelation":round(score,4)})
  result["tempo_candidates"] = sorted(candidates,key=lambda row:row["autocorrelation"],reverse=True)[:6]
  result["tempo_status"] = "signal_estimates_only; half/double tempo ambiguous; listening required"
  return result


def analyze(video, out, interval=8, max_frames=60, scene_threshold=.28, ffmpeg=None):
  if not math.isfinite(interval) or interval <= 0 or max_frames < 2 or not 0 < scene_threshold < 1:
    raise ValueError("interval>0、max_frames>=2，scene_threshold 必须在 0 与 1 之间。")
  video, out = Path(video).resolve(),Path(out).resolve()
  if out.exists() and any(out.iterdir()):
    raise ValueError("分析目录不为空，请换一个输出目录。")
  out.mkdir(parents=True,exist_ok=True)
  (out/"frames").mkdir()
  ffmpeg = ffmpeg_path(ffmpeg)
  metadata = probe(video,ffmpeg)
  if not metadata["width"]:
    raise ValueError("输入文件没有可用的视频轨。")
  interval = max(interval,metadata["duration"]/(max_frames-1))
  filters = "select='isnan(prev_selected_t)+gte(t-prev_selected_t,{})',scale=480:-2,showinfo".format(interval)
  process = subprocess.run([ffmpeg,"-hide_banner","-i",str(video),"-vf",filters,"-fps_mode","vfr",
                            "-frames:v",str(max_frames),str(out/"frames/frame-%03d.jpg")],capture_output=True,text=True)
  if process.returncode:
    raise ValueError(process.stderr[-3000:])
  (out/"frames.log").write_text(process.stderr,encoding="utf-8")
  times = [float(value) for value in re.findall(r"pts_time:([\d.]+)",process.stderr)]
  paths = sorted((out/"frames").glob("*.jpg"))
  with Image.open(paths[0]) as first:
    width,height = first.size
  columns = min(4,len(paths))
  sheet = Image.new("RGB",(columns*width,math.ceil(len(paths)/columns)*(height+28)),"#151b27")
  draw = ImageDraw.Draw(sheet)
  for index,path in enumerate(paths):
    x,y = index%columns*width,index//columns*(height+28)
    with Image.open(path) as frame:
      sheet.paste(frame,(x,y))
    draw.text((x+8,y+height+7),"{:.3f}s".format(times[index]),fill="white")
  sheet.save(out/"contact-sheet.jpg",quality=90)
  changes = subprocess.run([ffmpeg,"-hide_banner","-i",str(video),"-vf",
    "select='gt(scene,{})',showinfo".format(scene_threshold),"-an","-f","null","-"],capture_output=True,text=True)
  if changes.returncode:
    raise ValueError(changes.stderr[-3000:])
  raw_cuts = [float(value) for value in re.findall(r"pts_time:([\d.]+)",changes.stderr)]
  grouped_cuts = []
  for time in raw_cuts:
    if not grouped_cuts or time-grouped_cuts[-1] > .4:
      grouped_cuts.append(time)
  result = {"source_name":video.name,"metadata":{key:value for key,value in metadata.items() if key != "raw_metadata"},
            "frame_times":times,"scene_threshold":scene_threshold,"raw_scene_candidates":raw_cuts,
            "grouped_scene_candidates":grouped_cuts,"notes":["Scene candidates are not a verified edit decision list.",
              "No speech recognition, lyric alignment, or listening analysis was performed by this script."]}
  if metadata["has_audio"]:
    wav = out/"audio-mono-16k.wav"
    subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-i",str(video),"-vn","-ac","1","-ar","16000",
                    "-c:a","pcm_s16le",str(wav)],check=True)
    result["audio"] = audio_stats(wav)
  (out/"analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  (out/"metadata.txt").write_text(metadata["raw_metadata"],encoding="utf-8")
  return result


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("video")
  parser.add_argument("--out",required=True)
  parser.add_argument("--interval",type=float,default=8)
  parser.add_argument("--max-frames",type=int,default=60)
  parser.add_argument("--scene-threshold",type=float,default=.28)
  parser.add_argument("--ffmpeg")
  args = parser.parse_args()
  try:
    result = analyze(args.video,args.out,args.interval,args.max_frames,args.scene_threshold,args.ffmpeg)
    print(json.dumps({"duration":result["metadata"]["duration"],"frames":len(result["frame_times"]),
                       "scene_candidates":len(result["grouped_scene_candidates"]),"out":str(Path(args.out).resolve())},indent=2))
  except (ValueError,OSError,subprocess.SubprocessError) as error:
    parser.exit(2,str(error)+"\n")


if __name__ == "__main__":
  main()
