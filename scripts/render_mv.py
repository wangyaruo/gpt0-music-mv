#!/usr/bin/env python3
"""Render a deterministic pixel-RPG lyric MV with optional user-provided audio."""
import argparse
import copy
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
from narrative_events import prepare_events, scroll_position, state_at
from pixel_world import KIND_NAMES, PALETTES, RAIN_KINDS, scene_frame, sprite


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
  if type(config.get("animation_fps", 8)) is not int or not 1 <= config.get("animation_fps", 8) <= 30:
    raise ValueError("animation_fps 必须是 1–30 的整数。")
  if config.get("subtitle_mode", "dialogue") not in ("dialogue", "karaoke"):
    raise ValueError("subtitle_mode 必须为 dialogue 或 karaoke。")
  if not finite_number(config.get("bpm", 120)) or not 30 <= config.get("bpm", 120) <= 240:
    raise ValueError("bpm 必须在 30–240 之间；估计值需人工校准。")
  if not finite_number(config.get("beat_offset", 0)):
    raise ValueError("beat_offset 必须是有限数。")
  scenes = config.get("scenes", [])
  if not scenes:
    raise ValueError("至少需要一个场景。")
  cursor = 0
  tracks = {}
  coin_tracks = {}
  camera_tracks = {}
  for scene in scenes:
    if not all(finite_number(scene.get(key)) for key in ("start", "end")):
      raise ValueError("场景 start/end 必须是有限数。")
    if abs(scene["start"]-cursor) > .00001 or scene["end"] <= scene["start"]:
      raise ValueError("场景时间轴必须连续且不重叠。")
    if scene.get("kind") not in KIND_NAMES or scene.get("palette", "day") not in PALETTES:
      raise ValueError("未知场景 kind 或 palette。")
    if scene.get("action", "idle") not in ("idle", "walk", "jump", "play"):
      raise ValueError("未知 action。")
    if "partner" in scene and type(scene["partner"]) is not bool:
      raise ValueError("partner 必须是布尔值。")
    if any(not isinstance(scene[key], str) for key in ("label", "era_label") if key in scene):
      raise ValueError("label 和 era_label 必须是字符串。")
    narrative_time = scene.get("narrative_time", "present")
    branch = scene.get("branch", "main")
    if narrative_time not in ("present", "memory", "alternate") or not isinstance(branch, str) or not branch.strip():
      raise ValueError("narrative_time 或 branch 无效。")
    track = (narrative_time, branch)
    change = scene.get("state", {})
    if not isinstance(change, dict) or set(change) - {"party", "affinity", "distance", "inventory", "gauges"}:
      raise ValueError("state 仅支持 party、affinity、distance、inventory、gauges。")
    if "party" in change and (not isinstance(change["party"], list) or
        any(not isinstance(value, str) or value not in ("hero", "partner") for value in change["party"]) or
        len(set(change["party"])) != len(change["party"])):
      raise ValueError("party 必须是 hero/partner 的不重复列表。")
    if "inventory" in change and (not isinstance(change["inventory"], list) or
        any(not isinstance(item, str) or not item for item in change["inventory"])):
      raise ValueError("inventory 必须是非空字符串列表。")
    if "affinity" in change and (not finite_number(change["affinity"]) or not 0 <= change["affinity"] <= 100):
      raise ValueError("affinity 必须在 0–100 之间。")
    if "distance" in change:
      distance = change["distance"]
      if (not isinstance(distance, dict) or set(distance) != {"value", "unit"} or
          not finite_number(distance["value"]) or distance["value"] < 0 or distance["unit"] not in ("km", "m", "cm")):
        raise ValueError("distance 需要非负 value 和 km/m/cm 单位。")
    if "gauges" in change:
      gauges = change["gauges"]
      if (not isinstance(gauges, dict) or len(gauges) > 2 or
          any(not isinstance(name, str) or not 1 <= len(name) <= 8 or not finite_number(value) or not 0 <= value <= 100
              for name, value in gauges.items())):
        raise ValueError("gauges 最多两个，名称不超过 8 字，数值在 0–100 之间。")
    state = copy.deepcopy(tracks.get(track, {}))
    event = scene.get("event", "")
    if not isinstance(event, str):
      raise ValueError("event 必须是说明状态变化的字符串。")
    if any(key in state and state[key] != value for key, value in change.items()) and not event.strip():
      raise ValueError("已有状态发生变化时，必须填写 event 说明原因。")
    state.update(change)
    scene["_state"] = copy.deepcopy(state)
    if "party" in state and "partner" not in scene:
      scene["partner"] = "partner" in state["party"]
    last_coins = coin_tracks.get(track, 0)
    coins = scene.get("coins", last_coins)
    if type(coins) is not int or coins < 0 or (coins < last_coins and not event.strip()):
      raise ValueError("coins 必须非负；减少时必须通过 event 说明原因。")
    scene["coins"] = coins
    scene["_animation_fps"] = config.get("animation_fps", 8)
    if any(scene.get(key, "front") not in ("front", "back", "left", "right") for key in ("hero_view", "partner_view")):
      raise ValueError("角色视角必须为 front/back/left/right。")
    if scene.get("weather", "clear") not in ("clear", "rain") or scene.get("bus", "none") not in ("none", "approach", "leave"):
      raise ValueError("weather 或 bus 类型无效。")
    if scene.get("weather") == "rain" and scene["kind"] not in ("rain_city", "bus_stop"):
      raise ValueError("当前雨层仅支持 rain_city 和 bus_stop。")
    if scene.get("bus", "none") != "none" and scene["kind"] != "bus_stop":
      raise ValueError("当前公交进出动画仅支持 bus_stop。")
    if "umbrella" in scene:
      item = scene["umbrella"]
      if (not isinstance(item, dict) or item.get("owner", "shared") not in ("hero", "partner", "shared") or
          item.get("color", "blue") not in ("blue", "pink")):
        raise ValueError("umbrella 需要有效的 owner 和 color。")
      if scene["kind"] not in ("rain_city", "bus_stop", "classroom", "bookstore"):
        raise ValueError("当前雨伞仅支持雨夜城市、站台、教室和书店场景。")
      if item.get("owner") in ("partner", "shared") and not scene.get("partner"):
        raise ValueError("同伴或共用雨伞需要同伴出现在场景中。")
    if "dialogue" in scene and "choice" in scene:
      raise ValueError("同一场景的 dialogue 和 choice 会重叠，请拆分场景。")
    if "dialogue" in scene:
      dialogue = scene["dialogue"]
      if (not isinstance(dialogue, dict) or not isinstance(dialogue.get("text"), str) or
          not isinstance(dialogue.get("name", ""), str) or dialogue.get("speaker", "hero") not in ("hero", "partner")):
        raise ValueError("dialogue 需要 text、可选 name 和有效的 speaker。")
    if "choice" in scene:
      choice = scene["choice"]
      if (not isinstance(choice, dict) or not isinstance(choice.get("prompt"), str) or
          not isinstance(choice.get("options"), list) or not 2 <= len(choice["options"]) <= 3 or
          any(not isinstance(option, str) or not option for option in choice["options"]) or
          type(choice.get("selected")) is not int or not 0 <= choice["selected"] < len(choice["options"])):
        raise ValueError("choice 需要 prompt、2–3 个选项和有效的 selected 下标。")
    end_state, end_coins = prepare_events(scene, state, coins)
    if (scene.get("dialogue") or scene.get("choice")) and any(
        item["kind"] in ("checkpoint", "stage_clear") for item in scene.get("events", [])):
      raise ValueError("对白/选择与 checkpoint/stage_clear 会重叠，请拆分场景。")
    tracks[track], coin_tracks[track] = end_state, end_coins
    if scene["kind"] == "candy_road":
      camera = scene.get("camera", {})
      if not isinstance(camera, dict) or set(camera) - {"world", "speed", "offset"}:
        raise ValueError("camera 仅支持 world、speed 和 offset。")
      world = camera.get("world", "main")
      if not isinstance(world, str) or not world.strip():
        raise ValueError("camera.world 必须是非空字符串。")
      camera_key = (narrative_time, branch, world)
      previous = camera_tracks.get(camera_key, {"offset": 0, "speed": 8})
      speed, offset = camera.get("speed", previous["speed"]), camera.get("offset", previous["offset"])
      if not finite_number(speed) or not -40 <= speed <= 40 or not finite_number(offset):
        raise ValueError("camera.speed 需要在 -40–40 之间，offset 必须是有限数。")
      scene["_scroll_start"], scene["_scroll_speed"] = offset, speed
      camera_tracks[camera_key] = {"offset": scroll_position(scene, scene["end"]), "speed": speed}
    elif "camera" in scene:
      raise ValueError("camera 目前仅支持 candy_road。")
    cursor = scene["end"]
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
    mode = lyric.get("mode", config.get("subtitle_mode", "dialogue"))
    if mode not in ("dialogue", "karaoke"):
      raise ValueError("字幕模式必须为 dialogue 或 karaoke。")
    lyric["_mode"] = mode
    tokens = lyric.get("tokens", [])
    if not isinstance(tokens, list) or (tokens and mode != "karaoke"):
      raise ValueError("tokens 必须是卡拉 OK 模式下的列表。")
    if tokens:
      position = lyric["start"]
      for token in tokens:
        if (not isinstance(token, dict) or not isinstance(token.get("text"), str) or not token["text"] or
            not all(finite_number(token.get(key)) for key in ("start", "end")) or
            not position <= token["start"] < token["end"] <= lyric["end"]):
          raise ValueError("歌词 tokens 必须有不重叠、在句内的 start/end 和非空 text。")
        position = token["end"]
      if "".join(token["text"] for token in tokens) != lyric["text"]:
        raise ValueError("所有 token 的 text 拼接后必须与整句歌词一致。")
    if lyric.get("timing_source", "estimated") not in ("manual", "aligned", "estimated"):
      raise ValueError("timing_source 必须为 manual/aligned/estimated。")
    highlights = lyric.get("highlights", [])
    if not isinstance(highlights, list):
      raise ValueError("highlights 必须为列表。")
    end_index = 0
    for highlight in highlights:
      if (not isinstance(highlight, dict) or type(highlight.get("start")) is not int or
          type(highlight.get("end")) is not int or not end_index <= highlight["start"] < highlight["end"] <= len(lyric["text"]) or
          not isinstance(highlight.get("color"), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", highlight["color"])):
        raise ValueError("highlights 需要按字符索引排序的不重叠区间和 #RRGGBB 颜色。")
      end_index = highlight["end"]
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


def layout_glyphs(text, font, width):
  """Keep original character indices across line breaks for karaoke coloring."""
  lines = [[]]
  current = ""
  for index, char in enumerate(text):
    if char == "\n":
      lines.append([])
      current = ""
    else:
      if font.getlength(current+char) > width and current:
        lines.append([])
        current = ""
      lines[-1].append((index, char))
      current += char
  return lines


def karaoke_states(lyric, time):
  """Return played/active/pending for each code point; timestamps are never inferred as verified."""
  text = lyric["text"]
  tokens = lyric.get("tokens", [])
  if tokens:
    result = []
    for token in tokens:
      status = "played" if time >= token["end"] else "active" if time >= token["start"] else "pending"
      result.extend([status]*len(token["text"]))
    return result
  if not text:
    return []
  if time < lyric["start"]:
    return ["pending"]*len(text)
  if time >= lyric["end"]:
    return ["played"]*len(text)
  relative = max(0.0, min(1.0, (time-lyric["start"])/(lyric["end"]-lyric["start"])))
  active = min(len(text)-1, int(relative*len(text)))
  return ["played" if index < active else "active" if index == active else "pending" for index in range(len(text))]


def lyric_color(lyric, index, status):
  colors = {"played": "#f3f3f6", "active": "#ff9dc0", "pending": "#7e87a2"}
  if status == "played":
    for highlight in lyric.get("highlights", []):
      if highlight["start"] <= index < highlight["end"]:
        return highlight["color"]
  return colors[status]


class Renderer:
  def __init__(self, config, font_path, base):
    self.config = config
    self.scale = config.get("scale", 4)
    self.size = (256*self.scale, 144*self.scale)
    self.font = ImageFont.truetype(font_path, 6*self.scale)
    self.small = ImageFont.truetype(font_path, 5*self.scale)
    self.title = ImageFont.truetype(font_path, 13*self.scale)
    self.lyrics = config.get("lyrics", [])
    def strings(value):
      if isinstance(value, str):
        return value
      if isinstance(value, dict):
        return "".join(strings(item) for item in value.values())
      if isinstance(value, list):
        return "".join(strings(item) for item in value)
      return ""
    all_text = strings(config)
    missing = bytes(self.font.getmask("\uffff"))
    for character in set(all_text):
      if "\u3400" <= character <= "\u9fff" and bytes(self.font.getmask(character)) == missing:
        raise ValueError("字体缺少汉字：" + character)
    for row in self.lyrics:
      margin = 16 if row["_mode"] == "karaoke" else 36
      row["glyphs"] = layout_glyphs(row["text"], self.font, self.size[0]-margin*self.scale)
      row["lines"] = ["".join(char for _, char in line) for line in row["glyphs"]]
      if len(row["glyphs"]) > 2:
        raise ValueError("字幕超过两行，请分句：" + row["text"])
    for scene in config["scenes"]:
      if scene.get("dialogue"):
        scene["dialogue"]["_lines"] = wrap_text(scene["dialogue"]["text"], self.small, self.size[0]-55*self.scale)
        if len(scene["dialogue"]["_lines"]) > 2:
          raise ValueError("剧情对白超过两行，请分句。")
      if scene.get("choice"):
        choice = scene["choice"]
        if self.small.getlength(choice["prompt"]) > 135*self.scale or any(
            self.small.getlength(option) > (135//len(choice["options"])-4)*self.scale for option in choice["options"]):
          raise ValueError("选择菜单文字过长，请缩短提示或选项。")
      for event in scene.get("events", []):
        if event["kind"] in ("checkpoint", "stage_clear") and self.font.getlength(
            event.get("text") or ("存档点" if event["kind"] == "checkpoint" else "STAGE CLEAR")) > 120*self.scale:
          raise ValueError("事件标题过长，请缩短。")
        if event["kind"] == "pickup" and self.small.getlength(event["item"]) > 70*self.scale:
          raise ValueError("收集物品名称过长，请缩短。")
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

  def overlays(self, image, draw, scene):
    k = self.scale
    state = scene.get("_state", {})
    status_width = 0
    summary = []
    if "party" in state:
      summary.append("队伍 {}".format(len(state["party"])))
    if "affinity" in state:
      summary.append("好感 {:g}".format(state["affinity"]))
    if "distance" in state:
      summary.append("距离 {:g}{}".format(state["distance"]["value"], state["distance"]["unit"]))
    if "inventory" in state:
      summary.append("物品 {}".format(len(state["inventory"])))
    gauges = state.get("gauges", {})
    if summary:
      text = " · ".join(summary)
      if self.small.getlength(text) > 155*k:
        raise ValueError("状态面板过长；请精简状态或缩短数值。")
      width = self.small.getlength(text)+5*k
      status_width = width+4*k
      status_y = 14 if gauges or scene["kind"] == "candy_road" else 3
      if len(gauges) == 2 and status_width > 95*k:
        raise ValueError("状态面板与第二个进度条重叠，请精简状态。")
      draw.rectangle((4*k,status_y*k,4*k+width,(status_y+9)*k),
                     fill="#112039", outline="#b7c6d3", width=max(1,k//3))
      self.text(draw,(6*k,(status_y+1)*k),text,self.small,color="#ebedf0")
    for index, (name, value) in enumerate(gauges.items()):
      if self.small.getlength(name) > 35*k:
        raise ValueError("进度条名称显示过长，请缩短。")
      y = (3+index*10)*k
      draw.rectangle((99*k,y,197*k,y+8*k),fill="#112039",outline="#b7c6d3",width=max(1,k//3))
      self.text(draw,(101*k,y+k),name,self.small,color="#f3d6e3")
      draw.rectangle((137*k,y+2*k,173*k,y+6*k),fill="#4b344c")
      if value > 0:
        draw.rectangle((137*k,y+2*k,(137+36*value/100)*k,y+6*k),fill="#e984af")
      self.text(draw,(175*k,y+k),"{}%".format(round(value)),self.small,color="#f7e3ec")
    if scene["kind"] in RAIN_KINDS and scene.get("label"):
      label = scene["label"]
      if not gauges and status_width+self.small.getlength(label) > 238*k:
        raise ValueError("场景名称与状态面板重叠，请缩短。")
      if gauges and self.small.getlength(label) > 46*k:
        raise ValueError("场景名称与进度条重叠，请缩短。")
      self.text(draw,(247*k,4*k),label,self.small,anchor="rt")
    if scene.get("narrative_time") in ("memory", "alternate"):
      label = scene.get("era_label", "回忆" if scene["narrative_time"] == "memory" else "另一种可能")
      width = self.small.getlength(label)+5*k
      draw.rectangle((4*k,108*k,4*k+width,117*k),fill="#50463f",outline="#d7c7ae",width=max(1,k//3))
      self.text(draw,(6*k,109*k),label,self.small,color="#fff3da")
    if scene["kind"] == "memory_items":
      for index, item in enumerate(state.get("inventory", [])[:3]):
        if self.small.getlength(item) > 53*k:
          raise ValueError("记忆物品名称过长，请缩短。")
        self.text(draw,((64+62*index)*k,95*k),item,self.small,anchor="mt")
    if scene["kind"] == "city_map":
      self.text(draw,(40*k,104*k),"城市",self.small,anchor="mt")
      self.text(draw,(210*k,104*k),"远方",self.small,anchor="mt")
    dialogue = scene.get("dialogue")
    if dialogue:
      draw.rectangle((6*k,20*k,250*k,48*k),fill="#10213a",outline="#d5d5ca",width=max(1,k//2))
      draw.rectangle((9*k,23*k,28*k,44*k),fill="#213d59",outline="#537a93",width=max(1,k//3))
      portrait = sprite(partner=dialogue.get("speaker") == "partner").crop((0,0,12,10))
      image.alpha_composite(portrait.resize((16*k,14*k),Image.Resampling.NEAREST),(10*k,25*k))
      self.text(draw,(33*k,22*k),dialogue.get("name",""),self.small,color="#f3aac4")
      for index, line in enumerate(dialogue["_lines"]):
        self.text(draw,(33*k,(29+7*index)*k),line,self.small,color="#e7edf3")
    choice = scene.get("choice")
    if choice:
      draw.rectangle((53*k,23*k,203*k,51*k),fill="#10213a",outline="#d5d5ca",width=max(1,k//2))
      self.text(draw,(59*k,27*k),choice["prompt"],self.small,color="#fff0d2")
      for index, option in enumerate(choice["options"]):
        x = 62+index*(135//len(choice["options"]))
        color = "#ffacc7" if index == choice["selected"] else "#abb6c7"
        self.text(draw,(x*k,38*k),("▶ " if index == choice["selected"] else "")+option,self.small,color=color)

  def event_overlays(self, draw, scene, time):
    k = self.scale
    for event in scene.get("events", []):
      if not event["start"] <= time < event["end"]:
        continue
      if event["kind"] in ("checkpoint", "stage_clear"):
        title = event.get("text") or ("存档点" if event["kind"] == "checkpoint" else "STAGE CLEAR")
        draw.rectangle((64*k,28*k,192*k,45*k),fill="#f4dfdc",outline="#805269",width=max(1,k//2))
        draw.text((128*k,31*k),title,font=self.font,fill="#493344",anchor="mt")
      elif event["kind"] == "pickup":
        self.text(draw,(128*k,52*k),"+{} {}".format(event.get("coins",1),event["item"]),
                  self.small,color="#ffe7a7",anchor="mt")
      elif event["kind"] == "fast_forward":
        draw.rectangle((201*k,15*k,250*k,25*k),fill="#f1be69",outline="#fcebc5",width=max(1,k//3))
        self.text(draw,(225*k,16*k),"▶▶ ×{:g}".format(event.get("factor",2)),self.small,
                  color="#553e59",anchor="mt")

  def frame(self, time):
    cfg, k = self.config, self.scale
    original = next(scene for scene in cfg["scenes"] if scene["start"] <= time < scene["end"])
    scene = dict(original)
    scene["_state"], scene["coins"] = state_at(original, time)
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
    elif kind not in RAIN_KINDS:
      self.text(draw, (47*k,5*k), "×{:02d}".format(scene["coins"]), self.small)
      self.text(draw, (247*k,5*k), scene.get("label",""), self.small, anchor="rt")
      if kind == "battle":
        self.text(draw, (81*k,23*k), "烦恼", self.small, color="#f984aa")
    self.overlays(image,draw,scene)
    self.event_overlays(draw,scene,time)
    lyric = next((row for row in self.lyrics if row["start"] <= time < row["end"]), None)
    if lyric and lyric["_mode"] == "karaoke":
      states = karaoke_states(lyric,time)
      widths = [sum(self.font.getlength(char) for _, char in line) for line in lyric["glyphs"]]
      x = (self.size[0]-max(widths,default=0))/2-2*k
      y = (122 if len(widths) == 2 else 130)*k
      draw.rectangle((x,y,self.size[0]-x,141*k),fill="#11192c")
      draw.rectangle((x,140*k,self.size[0]-x,141*k),fill="#d66795")
      for line_index, line in enumerate(lyric["glyphs"]):
        pos = (self.size[0]-widths[line_index])/2
        for char_index, char in line:
          self.text(draw,(pos,y+(2+line_index*8)*k),char,self.font,
                    color=lyric_color(lyric,char_index,states[char_index]))
          pos += self.font.getlength(char)
    elif lyric:
      x, y, w, h = 6*k, 120*k, 244*k, 22*k
      draw.rectangle((x,y,x+w,y+h), fill="#10213a", outline="#d5d5ca", width=max(1,k//2))
      draw.rectangle((x+k,y+k,x+w-k,y+h-k), outline="#355570", width=max(1,k//2))
      draw.rectangle((x+2*k,y+3*k,x+17*k,y+18*k), fill="#213d59", outline="#537a93", width=1)
      portrait = sprite().crop((0,0,12,10)).resize((12*k,10*k), Image.Resampling.NEAREST)
      image.alpha_composite(portrait,(x+3*k,y+5*k))
      count = min(len(lyric["text"]), int((time-lyric["start"])/lyric["reveal_seconds"]*len(lyric["text"])))
      for index, line in enumerate(lyric["glyphs"]):
        pos = x+21*k
        for char_index, char in line:
          if char_index < count:
            self.text(draw,(pos,y+(3+index*8)*k),char,self.font,color=lyric_color(lyric,char_index,"played"))
          pos += self.font.getlength(char)
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
    if ((meta["width"],meta["height"]) != renderer.size or meta["has_audio"] != bool(audio_path) or
        meta["fps"] is None or abs(meta["fps"]-fps) > .01):
      raise ValueError("输出画面尺寸、帧率或音轨存在性未通过验证。")
    os.replace(movie,out)
  result = {"path":str(out),"duration":meta["duration"],"width":meta["width"],"height":meta["height"],
            "fps":meta["fps"],"has_audio":meta["has_audio"],"silent_preview":not bool(audio_path),
            "subtitle_timing":{
              "word_timed_lines":sum(bool(row.get("tokens")) for row in config.get("lyrics", [])),
              "approximate_lines":sum(not row.get("tokens") for row in config.get("lyrics", [])),
              "declared_sources":{source:sum(row.get("timing_source", "estimated") == source
                                             for row in config.get("lyrics", []))
                                  for source in ("manual", "aligned", "estimated")},
              "note":"Tokens reflect supplied timestamps; other character timing is approximate and needs listening review."
            },"font":font_path}
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
