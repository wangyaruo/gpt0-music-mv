"""Original procedural pixel scenery and sprites; logical canvas is 256 x 144."""
import math
import random
from functools import lru_cache
from PIL import Image, ImageDraw, ImageOps

SIZE = (256, 144)
PALETTES = {
  "day": {"top": (36, 166, 222), "bottom": (161, 224, 233), "sea": "#1979bd", "sand": "#f3d798",
          "wave": "#d4fff0", "leaf": "#249b65", "trunk": "#9d5540", "sun": "#fff4a8"},
  "sunset": {"top": (106, 37, 104), "bottom": (255, 174, 95), "sea": "#aa456f", "sand": "#e8a57e",
             "wave": "#ffd993", "leaf": "#48434d", "trunk": "#53404f", "sun": "#fff178"},
  "night": {"top": (11, 17, 43), "bottom": (67, 65, 111), "sea": "#25456c", "sand": "#9b96b3",
            "wave": "#b4cee6", "leaf": "#172238", "trunk": "#1d2239", "sun": "#f0e9c4"}
}
HERO = (
  "...KKKKK....", "..KKKKKKK...", ".KKKKKKKKK..", ".KKSSKSSKK..", ".KSSSSSSSK..",
  "..SWSSWS....", "..SSSSSSS...", "...SSMSS....", "....SSS.....", "..BBBBBBB...",
  ".SBBBWBBBS..", ".SBBBBBBBS..", "..BBBBBBB...", "...DDDDD....", "...DDDDD...."
)
PARTNER = (
  "...HHHHH....", "..HHHHHHH...", ".HHHHHHHHH..", ".HHSSSSSHH..", ".HSSSSSSSH..",
  ".HSSWSSWSH..", ".HSSSSSSSH..", ".HHSSMSSHH..", "..HHSSSHH...", "...OOOOO....",
  "..SOOOOOS...", "..OOOOOOO...", ".OOOOOOOOO..", "..OOOOOOO...", "...SSSSS...."
)
COLORS = {"K": "#242a3d", "H": "#754650", "S": "#fbd1aa", "W": "#28334a", "M": "#dc7c78",
          "B": "#44b4bf", "D": "#294b70", "O": "#ee9471"}
RAIN_KINDS = {"rain_city", "bus_stop", "bus_interior", "classroom", "bookstore", "memory_items", "city_map"}
KIND_NAMES = {"title", "beach", "equipment", "drive", "battle", "map", "spotlight", "night", "ending", "candy_road", "composite"} | RAIN_KINDS


@lru_cache(maxsize=64)
def sprite(partner=False, step=0, silhouette=False, view="front"):
  image = Image.new("RGBA", (12, 19))
  draw = ImageDraw.Draw(image)
  for y, row in enumerate(PARTNER if partner else HERO):
    for x, key in enumerate(row):
      if key != ".":
        draw.point((x, y), fill="#181d32" if silhouette else COLORS[key])
  if view == "back":
    hair = "#181d32" if silhouette else COLORS["H" if partner else "K"]
    draw.rectangle((2, 3, 9, 8), fill=hair)
    if partner:
      draw.rectangle((1, 7, 10, 10), fill=hair)
  elif view in ("left", "right"):
    skin = "#181d32" if silhouette else COLORS["S"]
    draw.rectangle((3, 4, 8, 8), fill=skin)
    draw.point((4 if view == "left" else 7, 5), fill="#28334a")
  color = "#181d32" if silhouette else "#fbd1aa" if partner else "#294b70"
  shift = 1 if step % 2 else 0
  draw.rectangle((3 - shift, 15, 4, 17), fill=color)
  draw.rectangle((7, 15, 8 + shift, 17), fill=color)
  draw.rectangle((2 - shift, 18, 4, 18), fill="#252a40")
  draw.rectangle((7, 18, 9 + shift, 18), fill="#252a40")
  return image


def person(image, x, ground, time, partner=False, action="idle", zoom=1, silhouette=False, view="front", animation_fps=8, sprites=None):
  tick = int(time * animation_fps)
  name = "partner" if partner else "hero"
  if sprites and sprites.has(name):
    frame, anchor = sprites.frame(name, action, view, time)
  else:
    frame, anchor = sprite(partner, tick % 2 if action == "walk" else 0, silhouette, view), (6, 19)
  if zoom != 1:
    frame = frame.resize((frame.width * zoom, frame.height * zoom), Image.Resampling.NEAREST)
  hop = 0
  if action == "jump":
    phase = time % 1.6 / 1.6
    hop = int(20 * 4 * phase * (1 - phase))
  elif action in ("walk", "play"):
    hop = tick % 2
  image.alpha_composite(frame, (int(x - anchor[0] * zoom), int(ground - anchor[1] * zoom - hop)))
  if action == "play":
    draw = ImageDraw.Draw(image)
    draw.ellipse((int(x - 6), int(ground - 12 - hop), int(x + 1), int(ground - 5 - hop)), fill="#f5bc4c", outline="#604236")
    draw.line((int(x - 1), int(ground - 9 - hop), int(x + 10), int(ground - 14 - hop)), fill="#815d46", width=2)


def heart(draw, x, y, color="#e96994", size=1):
  for row, pixels in enumerate(("0110110", "1111111", "1111111", "0111110", "0011100", "0001000")):
    for col, pixel in enumerate(pixels):
      if pixel == "1":
        draw.rectangle((x + col * size, y + row * size, x + (col + 1) * size - 1,
                        y + (row + 1) * size - 1), fill=color)


def palm(draw, x, y, palette, time):
  lean = int(math.sin(time * .9 + x) * 1)
  draw.polygon([(x, y), (x + 4, y), (x + 10, y - 31), (x + 6, y - 34)], fill=palette["trunk"])
  for dy in range(4, 30, 5):
    draw.line((x + 2 + dy // 6, y - dy, x + 5 + dy // 6, y - dy), fill="#613e48")
  crown = x + 9 + lean
  for points in (
    [(crown, y-33), (crown-13, y-40), (crown-22, y-36), (crown-22, y-30), (crown-14, y-35)],
    [(crown, y-33), (crown+10, y-42), (crown+19, y-39), (crown+21, y-31), (crown+12, y-36)],
    [(crown, y-33), (crown-2, y-46), (crown-10, y-48), (crown-15, y-44), (crown-6, y-43)],
    [(crown, y-33), (crown+13, y-32), (crown+19, y-26), (crown+15, y-23), (crown+9, y-29)]):
    draw.polygon(points, fill=palette["leaf"])
  draw.rectangle((crown-1, y-35, crown+3, y-31), fill="#825442")


def note(draw, x, y, color="#fff1ac"):
  x, y = int(x), int(y)
  draw.rectangle((x+3, y-7, x+4, y), fill=color)
  draw.rectangle((x+4, y-7, x+7, y-5), fill=color)
  draw.rectangle((x, y-1, x+3, y+1), fill=color)


def sparkles(draw, time, center=(174, 90), color="#fff1aa", count=24):
  for index in range(count):
    phase = (time * .7 + index / count) % 1
    angle = index * 2.39996
    radius = 8 + phase * 43
    x = int(center[0] + math.cos(angle) * radius)
    y = int(center[1] + math.sin(angle) * radius * .7 - phase * 8)
    draw.rectangle((x, y, x + 1, y + 1), fill=color)


def background(time, palette_name):
  palette = PALETTES[palette_name]
  image = Image.new("RGBA", SIZE)
  draw = ImageDraw.Draw(image)
  for y in range(65):
    blend = round(y / 64 * 15) / 15
    color = tuple(round(a + (b-a)*blend) for a, b in zip(palette["top"], palette["bottom"]))
    draw.line((0, y, 255, y), fill=color)
    if y % 4 == 0 and y > 30:
      for x in range(y % 8, 256, 8):
        draw.point((x, y), fill=palette["bottom"])
  if palette_name == "night":
    rng = random.Random(48)
    for index in range(46):
      x, y = rng.randrange(256), rng.randrange(4, 59)
      if (int(time * 2) + index) % 7 != 0:
        draw.point((x, y), fill="#d8dcf2")
  sun_x, sun_y, radius = (181, 41, 22) if palette_name == "sunset" else (198, 30, 12)
  draw.ellipse((sun_x-radius, sun_y-radius, sun_x+radius, sun_y+radius), fill=palette["sun"])
  if palette_name != "night":
    for index, base in enumerate((14, 99, 220)):
      x = int((base - time * (1.2 + index*.3)) % 302) - 25
      y = 19 + index % 2 * 11
      draw.rectangle((x, y, x+31, y+5), fill="#fff2df")
      draw.rectangle((x+6, y-5, x+25, y+2), fill="#fff2df")
      draw.rectangle((x+12, y-8, x+22, y), fill="#fff2df")
  draw.rectangle((0, 64, 255, 95), fill=palette["sea"])
  for row in range(6):
    y = 67 + row*5
    for x in range(-32, 290, 42):
      start = int(x - (time * (5+row*.6)) % 42 + row*7)
      draw.rectangle((start, y, start+13, y+1), fill=palette["wave"])
    width = 3 + row*3
    draw.rectangle((sun_x-width, y+1, sun_x+width, y+2), fill=palette["sun"])
  draw.rectangle((0, 94, 255, 143), fill=palette["sand"])
  for x in range(0, 256, 8):
    y = 94 + int(math.sin(x*.15 + time*2)*1.5)
    draw.rectangle((x, y, x+7, y+1), fill=palette["wave"])
  rng = random.Random(17)
  for _ in range(210):
    x, y = rng.randrange(256), rng.randrange(98, 144)
    draw.point((x, y), fill="#b78382" if palette_name != "night" else "#77718e")
  palm(draw, 26, 110, palette, time)
  palm(draw, 230, 106, palette, time+1)
  return image


def scene_frame(scene, time, bpm, beat_offset=0):
  local = time - scene["start"]
  progress = min(1, max(0, local / (scene["end"] - scene["start"])))
  kind = scene["kind"]
  if kind == "composite":
    from layer_compositor import render
    return render(scene, time)
  if kind in RAIN_KINDS:
    from rain_scenes import render_rain_scene
    return render_rain_scene(scene, time)
  if kind == "candy_road":
    from candy_scenes import render_candy_scene
    return render_candy_scene(scene, time)
  palette_name = scene.get("palette", "night" if kind in ("night", "ending") else "day")
  image = background(time, palette_name)
  if scene.get("background_image") is not None:
    image = scene["background_image"].copy()
  draw = ImageDraw.Draw(image)
  beat = max(0, (time-beat_offset) * bpm / 60)
  if kind == "map":
    draw.rectangle((0, 0, 255, 143), fill="#246aa8")
    for y in range(8, 144, 8):
      for x in range(0, 256, 19):
        offset = int(time * 3) % 19
        draw.line((x-offset, y, x-offset+3, y), fill="#4298c7")
    points = ((42, 92), (132, 42), (215, 94))
    for index, (x,y) in enumerate(points):
      draw.ellipse((x-24, y-13, x+24, y+13), fill="#fbefbc")
      draw.ellipse((x-20, y-10, x+20, y+9), fill="#4ac976")
      draw.rectangle((x-4, y-4, x+4, y+4), fill="#e77677" if index == 0 else "#2e6d5a")
    for index in range(20):
      amount = index / 19
      x, y = 42 + amount*90, 92 - amount*50
      draw.rectangle((int(x),int(y),int(x)+1,int(y)+1), fill="#ffe4a0")
    person(image, 42 + progress*90, 86-progress*50, time, action="walk",
           view=scene.get("hero_view", "front"), animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
  elif kind == "equipment":
    draw.rectangle((0, 0, 255, 143), fill="#10223b")
    for x in range(-144, 256, 8):
      draw.line((x, 143, x+144, 0), fill="#18304a")
    draw.rectangle((8, 18, 113, 114), fill="#102b49", outline="#9caec1")
    draw.rectangle((121, 18, 247, 114), fill="#102139", outline="#9caec1")
    draw.ellipse((23, 91, 101, 105), fill="#23516a")
    person(image, 63, 101, time, action="idle", zoom=3,
           view=scene.get("hero_view", "front"), animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    row = int(local / 1.0) % 3
    draw.rectangle((125, 42+row*19, 243, 59+row*19), fill="#206b9c")
  elif kind == "drive":
    draw.rectangle((0, 104, 255, 119), fill="#5a5964")
    for x in range(-30, 280, 35):
      xx = int(x - time*38 % 35)
      draw.rectangle((xx, 114, xx+17, 115), fill="#f9eed3")
    x = 106 + int(math.sin(time*.7)*13)
    person(image, x+12, 103, time, view=scene.get("hero_view", "front"),
           animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    if scene.get("partner"):
      person(image, x-5, 103, time, partner=True, view=scene.get("partner_view", "front"),
             animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    draw.rectangle((x-28, 102, x+30, 111), fill="#ea787c", outline="#3c3549")
    draw.rectangle((x-16, 97, x+20, 102), fill="#d55b7a")
    draw.ellipse((x-18, 107, x-10, 115), fill="#28324b")
    draw.ellipse((x+17, 107, x+25, 115), fill="#28324b")
    draw.rectangle((x-15, 110, x-13, 112), fill="#d4e3df")
    draw.rectangle((x+20, 110, x+22, 112), fill="#d4e3df")
  elif kind == "battle":
    person(image, 75, 112, time, action="play", view=scene.get("hero_view", "front"),
           animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    if scene.get("partner"):
      person(image, 185, 112, time, partner=True, view=scene.get("partner_view", "front"),
             animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    draw.rectangle((78, 18, 231, 38), fill="#1b213b", outline="#aeb7c4")
    draw.rectangle((111, 27, 222, 30), fill="#4b2c4e")
    draw.rectangle((111, 27, 111+int(111*(1-progress)), 30), fill="#f16390")
    for index in range(4):
      phase = (local*.8 + index*.25) % 1
      note(draw, 91+phase*80, 90-int(math.sin(phase*math.pi)*16))
    heart(draw, 174, 78-int(beat%1*10), size=1)
  elif kind == "spotlight":
    draw.rectangle((0, 0, 255, 143), fill="#f3b62c")
    for index in range(16):
      a = index*math.pi/8 + local*.12
      b = a + math.pi/20
      draw.polygon([(128, 70), (128+int(math.cos(a)*300),70+int(math.sin(a)*300)),
                    (128+int(math.cos(b)*300),70+int(math.sin(b)*300))], fill="#ffe778")
    person(image, 128, 112, time, action="play", zoom=3, view=scene.get("hero_view", "front"),
           animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    sparkles(draw, time, center=(128,70), count=26)
  else:
    hero_x = 82 + int(progress*45) if kind == "beach" else 116
    action = scene.get("action", "walk" if kind == "beach" else "idle")
    person(image, hero_x, 112, time, action=action, view=scene.get("hero_view", "front"),
           animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    if scene.get("partner"):
      person(image, hero_x+28, 112, time+.2, partner=True, action="walk" if action == "walk" else "idle",
             view=scene.get("partner_view", "front"), animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
    if kind == "beach":
      for index in range(8):
        x = 92 + index*12
        y = 74-int(math.sin(index/7*math.pi)*17)
        width = 1+int(abs(math.cos(time*5 + index)) * 3)
        draw.rectangle((x-width,y,x+width,y+6),fill="#ffda58",outline="#a57435")
    if kind in ("night", "ending") and scene.get("partner"):
      heart(draw, hero_x+14, 81-int(math.sin(time*2)*3), color="#f4a5b4")
    if kind == "ending":
      draw.rectangle((174,99,199,114), fill="#f1bd43", outline="#3d3652")
      draw.rectangle((176,102,197,106), fill="#5e414d")
      draw.rectangle((185,104,189,109), fill="#fff6a4")
      draw.rectangle((174,91,199,98), fill="#e5a83b", outline="#3d3652")
      sparkles(draw, time, center=(187,98))
  if kind not in ("title", "equipment", "map", "spotlight", "ending"):
    for index in range(3):
      heart(draw, 8+index*9, 7)
    draw.rectangle((40,7,44,12), fill="#ffdf63", outline="#8a6a46")
  if scene.get("narrative_time") == "memory" and scene.get("memory_filter", True):
    image = ImageOps.colorize(image.convert("RGB").convert("L"), "#5f4a3d", "#f3e2bf").convert("RGBA")
  return image
