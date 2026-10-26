#!/usr/bin/env python3
"""Render a deterministic pixel-RPG lyric MV with optional user-provided audio."""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from media_utils import ffmpeg_path, probe
from pixel_world import KIND_NAMES, PALETTES, scene_frame, sprite


def parse_lrc(text, duration):
  offset_match = re.search(r"\[offset:([+-]?\d+)\]", text, re.I)
  offset = int(offset_match[1])/1000 if offset_match else 0
  rows = []
  pattern = re.compile(r"\[(\d+):(\d{1,2}(?:\.\d+)?)\]")
  for line in text.splitlines():
    matches = list(pattern.finditer(line))
    if not matches:
      continue
    lyric = pattern.sub("", line).strip()
    for match in matches:
      seconds = float(match[2])
      if seconds >= 60:
        raise ValueError("LRC 秒数必须小于 60。")
      time = int(match[1])*60+seconds+offset
      if not 0 <= time < duration:
        raise ValueError("LRC 时间戳超出成片范围，请调整 offset 或片长。")
      rows.append((time, lyric))
  rows.sort(key=lambda item: item[0])
  if not rows:
    raise ValueError("LRC 中没有可用的句级时间戳。")
  if any(rows[index][0] == rows[index-1][0] for index in range(1, len(rows))):
    raise ValueError("LRC 含重复时间戳；请合并该时刻的歌词。")
  return [{"start": time, "end": rows[index+1][0] if index+1 < len(rows) else duration, "text": text}
          for index, (time, text) in enumerate(rows) if text]


def finite_number(value):
  return type(value) in (int, float) and math.isfinite(value)


def validate(config):
  if not finite_number(config.get("duration")) or config["duration"] <= 0:
    raise ValueError("duration 必须是有限正数。")
  if type(config.get("scale", 4)) is not int or not 2 <= config.get("scale", 4) <= 8:
    raise ValueError("scale 必须是 2–8 的整数。")
  if type(config.get("fps", 30)) is not int or not 1 <= config.get("fps", 30) <= 60:
    raise ValueError("fps 必须是 1–60 的整数。")
  if not finite_number(config.get("bpm", 120)) or not 30 <= config.get("bpm", 120) <= 240:
    raise ValueError("bpm 必须在 30–240 之间；估计值需人工校准。")
  if not finite_number(config.get("beat_offset", 0)):
    raise ValueError("beat_offset 必须是有限数。")
  scenes = config.get("scenes", [])
  if not scenes:
    raise ValueError("至少需要一个场景。")
  cursor = 0
  last_coins = 0
  for scene in scenes:
    if not all(finite_number(scene.get(key)) for key in ("start", "end")):
      raise ValueError("场景 start/end 必须是有限数。")
    if abs(scene["start"]-cursor) > .00001 or scene["end"] <= scene["start"]:
      raise ValueError("场景时间轴必须连续且不重叠。")
    if scene.get("kind") not in KIND_NAMES or scene.get("palette", "day") not in PALETTES:
      raise ValueError("未知场景 kind 或 palette。")
    if scene.get("action", "idle") not in ("idle", "walk", "jump", "play"):
      raise ValueError("未知 action。")
    coins = scene.get("coins", last_coins)
    if type(coins) is not int or coins < last_coins:
      raise ValueError("coins 必须是非递减的非负整数。")
    scene["coins"] = coins
    last_coins, cursor = coins, scene["end"]
  if abs(cursor-config["duration"]) > .00001:
    raise ValueError("场景必须覆盖完整 duration。")
  cursor = 0
  for lyric in config.get("lyrics", []):
    if not all(finite_number(lyric.get(key)) for key in ("start", "end")):
      raise ValueError("字幕时间必须是有限数。")
    if not cursor <= lyric["start"] < lyric["end"] <= config["duration"]:
      raise ValueError("字幕必须按顺序、不重叠，且在片长内。")
    if not isinstance(lyric.get("text"), str):
      raise ValueError("字幕 text 必须为字符串。")
    reveal = lyric.get("reveal_seconds", min(1.5, (lyric["end"]-lyric["start"])*.65))
    if not finite_number(reveal) or not 0 < reveal <= lyric["end"]-lyric["start"]:
      raise ValueError("reveal_seconds 必须大于零且不超过句子时长。")
    lyric["reveal_seconds"] = reveal
    cursor = lyric["end"]


def find_font(explicit=None):
  candidates = [explicit, os.environ.get("MV_FONT"),
                "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "C:/Windows/Fonts/msyh.ttc"]
  for candidate in candidates:
    if candidate and Path(candidate).is_file():
      return str(Path(candidate).resolve())
  raise ValueError("缺少中文字体；请通过 --font 或 MV_FONT 指定支持中文的 TTF/TTC/OTF。")


def wrap_text(text, font, width):
  lines = [""]
  for character in text:
    if character == "\n":
      lines.append("")
    elif font.getlength(lines[-1]+character) <= width:
      lines[-1] += character
    else:
      lines.append(character)
  return lines


class Renderer:
  def __init__(self, config, font_path, base):
    self.config = config
    self.scale = config.get("scale", 4)
    self.size = (256*self.scale, 144*self.scale)
    self.font = ImageFont.truetype(font_path, 6*self.scale)
    self.small = ImageFont.truetype(font_path, 5*self.scale)
    self.title = ImageFont.truetype(font_path, 13*self.scale)
    self.lyrics = config.get("lyrics", [])
    all_text = config.get("title", "") + config.get("credit", "") + "".join(row["text"] for row in self.lyrics)
    missing = bytes(self.font.getmask("\uffff"))
    for character in set(all_text):
      if "\u3400" <= character <= "\u9fff" and bytes(self.font.getmask(character)) == missing:
        raise ValueError("字体缺少汉字：" + character)
    for row in self.lyrics:
      row["lines"] = wrap_text(row["text"], self.font, self.size[0]-36*self.scale)
      if len(row["lines"]) > 2:
        raise ValueError("字幕超过两行，请分句：" + row["text"])
    for scene in config["scenes"]:
      if scene.get("background"):
        with Image.open(base / scene["background"]) as image:
          scene["background_image"] = image.convert("RGBA").resize((256,144), Image.Resampling.NEAREST)
    self.crt_overlay = Image.new("RGBA", self.size)
    draw = ImageDraw.Draw(self.crt_overlay)
    for y in range(0, self.size[1], self.scale):
      draw.line((0,y,self.size[0],y), fill=(5,8,20,18))
    for i in range(6):
      draw.rectangle((i,i,self.size[0]-1-i,self.size[1]-1-i), outline=(3,5,15,80-i*10))

  def text(self, draw, position, text, font=None, color="#fff1cc", anchor=None):
    draw.text(position, text, font=font or self.font, fill=color, stroke_width=max(1,self.scale//2),
              stroke_fill="#26344d", anchor=anchor)

  def frame(self, time):
    cfg, k = self.config, self.scale
    scene = next(scene for scene in cfg["scenes"] if scene["start"] <= time < scene["end"])
    image = scene_frame(scene, time, cfg.get("bpm",120), cfg.get("beat_offset",0))
    image = image.resize(self.size, Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    local = time-scene["start"]
    kind = scene["kind"]
    if kind == "title":
      title = cfg.get("title", "新的旅程")
      self.text(draw, (128*k,29*k), title[:max(1,int(local*6))], self.title, color="#ffe58b", anchor="mt")
      if int(local*2)%2 == 0:
        self.text(draw, (128*k,70*k), "PRESS START", self.small, anchor="mt")
    elif kind == "equipment":
      self.text(draw, (13*k,23*k), "装备", self.small, color="#ecdf85")
      self.text(draw, (127*k,23*k), "角色", self.small, color="#ecdf85")
      for index, text in enumerate(("上衣    海风衬衫", "手持    旅行吉他", "状态    勇气 +1")):
        self.text(draw, (130*k,(44+index*19)*k), text, self.small)
    elif kind == "map":
      self.text(draw, (9*k,8*k), "世界地图", self.font, color="#f7df7b")
      self.text(draw, (148*k,57*k), scene.get("label","下一站"), self.small)
    elif kind == "spotlight":
      self.text(draw, (128*k,10*k), scene.get("label","勇气 MAX"), self.font, anchor="mt")
    elif kind == "ending":
      self.text(draw, (128*k,18*k), "任务完成", self.title, color="#ffe895", anchor="mt")
      self.text(draw, (128*k,39*k), cfg.get("credit",""), self.small, anchor="mt")
    else:
      self.text(draw, (47*k,5*k), "×{:02d}".format(scene["coins"]), self.small)
      self.text(draw, (247*k,5*k), scene.get("label",""), self.small, anchor="rt")
      if kind == "battle":
        self.text(draw, (81*k,23*k), "烦恼", self.small, color="#f984aa")
    lyric = next((row for row in self.lyrics if row["start"] <= time < row["end"]), None)
    if lyric:
      x, y, w, h = 6*k, 120*k, 244*k, 22*k
      draw.rectangle((x,y,x+w,y+h), fill="#10213a", outline="#d5d5ca", width=max(1,k//2))
      draw.rectangle((x+k,y+k,x+w-k,y+h-k), outline="#355570", width=max(1,k//2))
      draw.rectangle((x+2*k,y+3*k,x+17*k,y+18*k), fill="#213d59", outline="#537a93", width=1)
      portrait = sprite().crop((0,0,12,10)).resize((12*k,10*k), Image.Resampling.NEAREST)
      image.alpha_composite(portrait,(x+3*k,y+5*k))
      count = min(len(lyric["text"]), int((time-lyric["start"])/lyric["reveal_seconds"]*len(lyric["text"])))
      for index, line in enumerate(lyric["lines"]):
        self.text(draw, (x+21*k,y+(3+index*8)*k), line[:max(0,count)], self.font, color="#e7edf3")
        count -= len(line)
      if int(time*3)%2 == 0:
        draw.polygon([(x+w-7*k,y+h-5*k),(x+w-3*k,y+h-5*k),(x+w-5*k,y+h-3*k)],fill="#ecd668")
    if cfg.get("crt",True):
      image = Image.alpha_composite(image,self.crt_overlay)
      width,height = self.size
      image = image.transform(self.size,Image.Transform.QUAD,
        (-k,0,k,height,width-k,height-k,width+k,k),resample=Image.Resampling.NEAREST,fillcolor="#040711")
    return image.convert("RGB")


def render(config_path, out, audio=None, lyrics=None, font=None, ffmpeg=None, still=None, overwrite=False):
  config_path, out = Path(config_path).resolve(), Path(out).resolve()
  config = json.loads(config_path.read_text(encoding="utf-8"))
  base = config_path.parent
  lyric_path = Path(lyrics).resolve() if lyrics else base/config["lyrics_file"] if config.get("lyrics_file") else None
  if lyric_path:
    config["lyrics"] = parse_lrc(lyric_path.read_text(encoding="utf-8-sig"),config["duration"])
  validate(config)
  configured_font = font or (str(base/config["font"]) if config.get("font") else None)
  font_path = find_font(configured_font)
  renderer = Renderer(config,font_path,base)
  if out.exists() and not overwrite:
    raise ValueError("输出已存在；确认替换时加 --overwrite："+str(out))
  out.parent.mkdir(parents=True,exist_ok=True)
  if still is not None:
    if not 0 <= still < config["duration"]:
      raise ValueError("单帧时间必须在片长内。")
    renderer.frame(still).save(out)
    return {"type":"still","path":str(out),"time":still}
  ffmpeg = ffmpeg_path(ffmpeg)
  audio_path = Path(audio).resolve() if audio else base/config["audio"] if config.get("audio") else None
  if audio_path:
    audio_meta = probe(audio_path,ffmpeg)
    if not audio_meta["has_audio"] or audio_meta["duration"]+.05 < config["duration"]:
      raise ValueError("指定音频没有音轨或短于片长；请修正分镜，不会静默截短或补静音。")
  fps = config.get("fps",30)
  frames = math.ceil(config["duration"]*fps)
  with tempfile.TemporaryDirectory(prefix=".pixel-mv-",dir=out.parent) as temporary:
    tmp = Path(temporary)
    movie = tmp/"render.mp4"
    command = [ffmpeg,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
               "-s","{}x{}".format(*renderer.size),"-r",str(fps),"-i","pipe:0"]
    if audio_path:
      command += ["-i",str(audio_path),"-map","0:v:0","-map","1:a:0","-c:a","aac","-b:a","192k"]
    else:
      command += ["-an"]
    command += ["-t",str(config["duration"]),"-c:v","libx264","-preset","fast","-crf","18",
                "-pix_fmt","yuv420p","-movflags","+faststart",str(movie)]
    with (tmp/"ffmpeg.log").open("w+b") as log:
      process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
      try:
        for index in range(frames):
          process.stdin.write(renderer.frame(index/fps).tobytes())
          if index % max(1,fps*4) == 0:
            print("render {:.1f}s / {:.1f}s".format(index/fps,config["duration"]),flush=True)
        process.stdin.close()
        code = process.wait(timeout=120)
        if code:
          log.seek(0)
          raise ValueError("FFmpeg 编码失败："+log.read().decode(errors="replace")[-3000:])
      except BaseException:
        if process.poll() is None:
          process.kill()
        process.wait()
        raise
    meta = probe(movie,ffmpeg)
    if abs(meta["duration"]-config["duration"]) > max(.1,1/fps):
      raise ValueError("输出时长未通过验证。")
    if (meta["width"],meta["height"]) != renderer.size or meta["has_audio"] != bool(audio_path):
      raise ValueError("输出画面尺寸或音轨存在性未通过验证。")
    os.replace(movie,out)
  result = {"path":str(out),"duration":meta["duration"],"width":meta["width"],"height":meta["height"],
            "fps":meta["fps"],"has_audio":meta["has_audio"],"silent_preview":not bool(audio_path),
            "subtitle_timing":"line-timed; character reveal is a reading animation","font":font_path}
  out.with_suffix(".render.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  return result


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("storyboard")
  parser.add_argument("--out",required=True)
  parser.add_argument("--audio")
  parser.add_argument("--lyrics")
  parser.add_argument("--font")
  parser.add_argument("--ffmpeg")
  parser.add_argument("--still",type=float)
  parser.add_argument("--overwrite",action="store_true")
  args = parser.parse_args()
  try:
    result = render(args.storyboard,args.out,args.audio,args.lyrics,args.font,args.ffmpeg,args.still,args.overwrite)
    print(json.dumps(result,ensure_ascii=False,indent=2))
  except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
    parser.exit(2,str(error)+"\n")


if __name__ == "__main__":
  main()
