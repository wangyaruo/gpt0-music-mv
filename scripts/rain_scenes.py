"""Original rainy-city pixel scenes. State and UI are applied by the common renderer."""
import math
import random
from PIL import Image, ImageDraw, ImageOps
from pixel_world import SIZE, heart, person


def city(time):
  image = Image.new("RGBA", SIZE, "#101a37")
  draw = ImageDraw.Draw(image)
  for band in range(4):
    draw.rectangle((0, band*18, 255, band*18+18), fill=(16+band*3, 25+band*3, 52+band*4))
  rng = random.Random(91)
  for left in range(-10, 270, 18):
    width = rng.randint(13, 19)
    top = rng.randint(27, 52)
    draw.rectangle((left, top, left+width, 94), fill=rng.choice(("#273553", "#30405e", "#354263")))
    for y in range(top+5, 88, 7):
      for x in range(left+3, left+width-1, 5):
        draw.rectangle((x, y, x+1, y+2), fill=rng.choice(("#f6dca1", "#536785", "#647590")))
  draw.rectangle((0, 87, 255, 96), fill="#38425b")
  draw.rectangle((0, 97, 255, 143), fill="#172039")
  draw.line((0, 97, 255, 97), fill="#aab4c9")
  for x in range(9, 256, 44):
    draw.rectangle((x, 118, x+23, 119), fill="#6e7893")
  for x in (22, 87, 151, 221):
    draw.line((x, 39, x, 96), fill="#a1b1ca", width=2)
    draw.rectangle((x-3, 39, x+3, 42), fill="#f8e8ba")
    draw.polygon([(x, 43), (x-10, 91), (x+10, 91)], fill="#667087")
    draw.line((x-9, 92, x+9, 92), fill="#a3b3c0")
  for index in range(24):
    x = (index*37+11)%256
    y = 102+(index*19)%38
    if int(time*4+index)%4 != 0:
      draw.line((x, y, x+3, y), fill="#8596b4")
  return image


def rain(image, time, foreground=False):
  draw = ImageDraw.Draw(image)
  count = 30 if foreground else 64
  speed = 34 if foreground else 22
  for i in range(count):
    x = (i*53 + int(time*(speed//3))) % 268 - 6
    y = (i*37 + int(time*speed)) % 142
    if foreground and 80 <= y <= 112 and 98 <= x <= 156:
      continue  # Keep faces and umbrellas readable.
    draw.line((x, y, x-2, y+5 if foreground else y+3), fill="#a1b8d4" if foreground else "#7087a9")


def umbrella(draw, center, top, color):
  main, light = ("#4b78c6", "#89b6ee") if color == "blue" else ("#dc80a0", "#f5b8cb")
  draw.polygon([(center-15, top+8), (center-11, top+2), (center, top-2),
                (center+11, top+2), (center+15, top+8)], fill=main, outline="#e3c5ca")
  draw.polygon([(center, top-2), (center-7, top+7), (center+2, top+7)], fill=light)
  draw.line((center, top+7, center, top+22), fill="#ded3c5")


def draw_bus(draw, x, y=71):
  x = int(x)
  draw.rectangle((x, y, x+74, y+28), fill="#329c9a", outline="#b9e0d9")
  draw.rectangle((x+3, y+5, x+51, y+17), fill="#ffe0a0")
  for pos in range(x+7, x+49, 10):
    draw.rectangle((pos, y+9, pos+4, y+17), fill="#4d526a")
  draw.rectangle((x+55, y+5, x+70, y+21), fill="#86c9d1")
  draw.ellipse((x+8, y+25, x+19, y+35), fill="#1e263b", outline="#a3b3c2")
  draw.ellipse((x+55, y+25, x+66, y+35), fill="#1e263b", outline="#a3b3c2")
  draw.rectangle((x+71, y+19, x+74, y+22), fill="#ffe7ac")


def interior(kind):
  image = Image.new("RGBA", SIZE, "#eadbc1")
  draw = ImageDraw.Draw(image)
  draw.rectangle((0, 0, 255, 95), fill="#eadbc1")
  draw.rectangle((0, 96, 255, 143), fill="#b78669")
  for y in range(99, 144, 8):
    draw.line((0, y, 255, y), fill="#9b725e")
  if kind == "classroom":
    draw.rectangle((12, 20, 124, 73), fill="#284c45", outline="#8b624b", width=3)
    draw.rectangle((158, 16, 236, 72), fill="#b9d4df", outline="#98755e", width=3)
    draw.line((197, 19, 197, 69), fill="#98755e", width=2)
    for x in (20, 81, 172):
      draw.rectangle((x, 102, x+35, 106), fill="#875f49")
      draw.line((x+4, 107, x+4, 119), fill="#875f49", width=2)
      draw.line((x+30, 107, x+30, 119), fill="#875f49", width=2)
  else:
    for left in (8, 90, 172):
      draw.rectangle((left, 15, left+74, 95), fill="#a68065", outline="#795e4e", width=3)
      for shelf in (35, 56, 77):
        draw.line((left+4, shelf, left+70, shelf), fill="#664e42", width=2)
        for col in range(left+7, left+67, 7):
          draw.rectangle((col, shelf-15, col+4, shelf-2), fill=(201+col%30, 181+col%30, 155+col%25))
  return image


def render_rain_scene(scene, time):
  kind = scene["kind"]
  local = time-scene["start"]
  progress = min(1, max(0, local/(scene["end"]-scene["start"])))
  weather = scene.get("weather", "rain" if kind in ("rain_city", "bus_stop") else "clear")
  if kind in ("classroom", "bookstore"):
    image = interior(kind)
  else:
    image = city(time)
  if scene.get("background_image") is not None:
    image = scene["background_image"].copy()
  draw = ImageDraw.Draw(image)
  if weather == "rain" and kind in ("rain_city", "bus_stop"):
    rain(image, time)
  if kind == "bus_stop":
    draw.rectangle((180, 58, 244, 99), outline="#a7c8c6", width=2)
    draw.rectangle((175, 55, 248, 59), fill="#4c9091")
    draw.rectangle((199, 90, 234, 93), fill="#b8a491")
    draw.line((190, 46, 190, 99), fill="#e9ddcb", width=2)
    draw.ellipse((185, 40, 195, 50), fill="#f0e7d9", outline="#d67989")
    bus = scene.get("bus", "none")
    if bus != "none":
      draw_bus(draw, -78+progress*118 if bus == "approach" else 20+progress*180)
  elif kind == "bus_interior":
    draw.rectangle((0, 0, 255, 143), fill="#53637c")
    draw.rectangle((6, 8, 249, 67), fill="#1c2945", outline="#a4b5c8", width=3)
    for x in range(16, 244, 15):
      for y in (18, 28, 39, 49):
        if (x+y)%4:
          draw.rectangle((x, y, x+2, y+4), fill="#f3d793")
    draw.rectangle((0, 73, 255, 105), fill="#327a82")
    draw.line((45, 0, 45, 119), fill="#e3bc63", width=2)
    draw.line((215, 0, 215, 119), fill="#e3bc63", width=2)
    for x in (20, 65, 108, 155, 196, 236):
      partner = x in (65, 196)
      person(image, x, 105, time, partner=partner,
             view=scene.get("partner_view" if partner else "hero_view", "front"),
             animation_fps=scene.get("_animation_fps", 8), sprites=scene.get("_sprite_assets"))
  elif kind == "memory_items":
    draw.rectangle((0, 0, 255, 143), fill="#14213d")
    for index, color in enumerate(("#7e9bb8", "#d99bb5", "#a8b08b")):
      x = 42+index*62
      draw.rectangle((x, 40, x+44, 92), outline="#92a3bc", width=2)
      if index < len(scene.get("_state", {}).get("inventory", [])):
        draw.rectangle((x+13, 51, x+30, 76), fill=color, outline="#e4dec7")
      else:
        draw.rectangle((x+19, 57, x+24, 67), fill="#6b7790")
  elif kind == "city_map":
    draw.rectangle((0, 0, 255, 143), fill="#cedbb6")
    draw.rectangle((22, 65, 40, 100), fill="#9e86c2")
    draw.rectangle((43, 53, 57, 100), fill="#9e86c2")
    draw.rectangle((196, 76, 225, 100), fill="#fff2d0", outline="#a67466")
    draw.polygon([(193, 76), (210, 62), (228, 76)], fill="#d17479")
    for x in range(59, 191, 10):
      y = 77-int(math.sin((x-59)/132*math.pi)*17)
      draw.line((x, y, x+4, y-2), fill="#d47b7b", width=2)
    draw.rectangle((60+int(progress*130), 72-int(math.sin(progress*math.pi)*17),
                    67+int(progress*130), 76-int(math.sin(progress*math.pi)*17)), fill="#3b8d94")
  if kind in ("rain_city", "bus_stop", "classroom", "bookstore"):
    animation_fps = scene.get("_animation_fps", 8)
    hero_x = 108+int(progress*16) if scene.get("action") == "walk" else 112
    person(image, hero_x, 113, time, action=scene.get("action", "idle"),
           view=scene.get("hero_view", "front"), animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
    if scene.get("partner"):
      person(image, hero_x+26, 113, time, partner=True, view=scene.get("partner_view", "front"),
             animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
    item = scene.get("umbrella")
    if item:
      owner = item.get("owner", "shared")
      center = hero_x if owner == "hero" else hero_x+26 if owner == "partner" else hero_x+13
      umbrella(draw, center, 81, item.get("color", "blue"))
    if scene.get("partner") and kind in ("rain_city", "bus_stop"):
      heart(draw, hero_x+16, 72-int(math.sin(time*2)*2), color="#f0a8bd")
  if weather == "rain" and kind in ("rain_city", "bus_stop"):
    rain(image, time, foreground=True)
  if scene.get("narrative_time") == "memory" and scene.get("memory_filter", True):
    image = ImageOps.colorize(image.convert("RGB").convert("L"), "#5f4a3d", "#f3e2bf").convert("RGBA")
  return image
