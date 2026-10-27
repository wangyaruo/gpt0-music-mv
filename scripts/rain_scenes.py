"""Original rainy-city pixel scenes. State and UI are applied by the common renderer."""
import math
import random
from PIL import Image, ImageDraw, ImageOps
from pixel_world import SIZE, heart, person, sprite


def city(time, wet=False):
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
    draw.polygon([(x, 44), (x-8, 91), (x+8, 91)], fill="#222e4b")
    draw.polygon([(x, 44), (x-4, 91), (x+4, 91)], fill="#2a3757")
    draw.line((x-9, 92, x+9, 92), fill="#a3b3c0")
  if wet:
    for index in range(24):
      x = (index*37+11)%256
      y = 102+(index*19)%38
      if int(time*4+index)%4 != 0:
        draw.line((x, y, x+3, y), fill="#8596b4")
  return image


def rain(image, time, foreground=False, density=1.0):
  if density <= 0.02:
    return
  draw = ImageDraw.Draw(image)
  count = 30 if foreground else 64
  speed = 34 if foreground else 22
  thin = density*10
  faint = density < 0.45
  for i in range(count):
    if (i % 10)+0.5 > thin:
      continue
    x = (i*53 + int(time*(speed//3))) % 268 - 6
    y = (i*37 + int(time*speed)) % 142
    if foreground and 80 <= y <= 112 and 98 <= x <= 156:
      continue  # Keep faces and umbrellas readable.
    if faint:
      draw.line((x, y, x-2, y+5 if foreground else y+3), fill="#8a9dba" if foreground else "#5e7391")
    else:
      draw.line((x, y, x-2, y+5 if foreground else y+3), fill="#a1b8d4" if foreground else "#7087a9")


def rain_density(scene, progress):
  """0 = 停，1 = 满。可填单个数值，也可填 [起, 止] 让雨在一个镜头内渐变。"""
  default = "rain" if scene.get("kind") in ("rain_city", "crossing") else "clear"
  if scene.get("weather", default) == "clear":
    return 0.0
  level = scene.get("rain_level", 1.0)
  if isinstance(level, (list, tuple)):
    level = level[0]+(level[1]-level[0])*progress
  return max(0.0, min(1.0, float(level)))


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


def night_tint(image, palette):
  """Recolour the same rainy street for the imagined golden-hour branch."""
  if palette not in ("sunset", "day"):
    return image
  wash = Image.new("RGB", SIZE, "#ff86a8" if palette == "sunset" else "#a9d4f0")
  return Image.blend(image.convert("RGB"), wash, .2).convert("RGBA")


def cloud_band(draw, base_y, shift, color, highlight):
  """One drifting layer of the cloud sea; a solid base keeps the band continuous."""
  draw.rectangle((0, base_y, 255, base_y+12), fill=color)
  for cluster in range(-1, 4):
    x = cluster*90-shift
    for dx, dy, width, height in ((0, 0, 26, 4), (16, -4, 32, 5), (40, -1, 26, 4), (56, 1, 18, 3)):
      draw.ellipse((x+dx, base_y+dy-height, x+dx+width, base_y+dy+height), fill=color)
    draw.ellipse((x+20, base_y-8, x+44, base_y-2), fill=highlight)
    draw.ellipse((x+42, base_y-5, x+58, base_y-1), fill=highlight)


def small_umbrella(draw, center, top, color):
  main, light = ("#4b78c6", "#89b6ee") if color == "blue" else ("#dc80a0", "#f5b8cb")
  draw.polygon([(center-9, top+5), (center-6, top+1), (center, top-1),
                (center+6, top+1), (center+9, top+5)], fill=main, outline="#e3c5ca")
  draw.polygon([(center, top-1), (center-4, top+5), (center+1, top+5)], fill=light)
  draw.line((center, top+4, center, top+13), fill="#ded3c5")


def tiny_person(image, x, ground, time, partner=False, silhouette=False, view="left"):
  """A smaller sprite for the far side of the street, so distance reads without a camera zoom."""
  frame = sprite(partner, int(time*8) % 2, silhouette, view)
  image.alpha_composite(frame.resize((8, 13), Image.Resampling.NEAREST), (int(x-4), int(ground-13)))


def rooftop(scene, time):
  """Above the cloud line: the only clear sky in this story."""
  local = time-scene["start"]
  span = max(.001, scene["end"]-scene["start"])
  progress = min(1, max(0, local/span))
  image = Image.new("RGBA", SIZE, "#080d22")
  draw = ImageDraw.Draw(image)
  for y in range(116):
    blend = y/115
    color = tuple(round(a+(b-a)*blend) for a, b in zip((6, 11, 32), (48, 40, 78)))
    draw.line((0, y, 255, y), fill=color)
  rng = random.Random(31)
  for index in range(42):
    x, y = rng.randrange(256), rng.randrange(3, 70)
    if (int(time*1.6)+index) % 9:
      draw.point((x, y), fill="#dfe4f7" if index % 3 else "#9aa6c8")
  draw.ellipse((188, 12, 208, 32), fill="#f5efda")
  draw.ellipse((193, 17, 197, 21), fill="#e6dfc7")
  draw.ellipse((200, 24, 203, 27), fill="#e6dfc7")
  draw.ellipse((190, 25, 192, 27), fill="#e6dfc7")
  for index in range(4):
    x = int((index*74-time*4) % 320)-32
    y = 40+index % 3*8
    draw.rectangle((x, y, x+38, y+1), fill="#2b3152")
  for index in range(30):
    x = index*11-14
    height = 6+(index*index % 20)
    draw.rectangle((x, 100-height, x+10, 100), fill="#121829")
    if index % 3 == 0:
      draw.point((x+3, 100-height+3), fill="#ffd98f")
      draw.point((x+6, 100-height+7), fill="#f0b46a")
  cloud_band(draw, 96, int(time*2.6) % 90, "#222a46", "#333d63")
  cloud_band(draw, 103, int(time*4.8) % 90, "#2e3757", "#455080")
  cloud_band(draw, 110, int(time*7.6) % 90, "#3d4870", "#5c6795")
  draw.rectangle((0, 116, 255, 143), fill="#1a2033")
  draw.line((0, 116, 255, 116), fill="#5a648b")
  draw.rectangle((0, 117, 255, 118), fill="#232a41")
  texture = random.Random(9)
  for index in range(110):
    x, y = texture.randrange(256), texture.randrange(121, 143)
    draw.point((x, y), fill="#252c44" if index % 2 else "#151b2c")
  for x in range(8, 256, 19):
    draw.line((x, 106, x, 116), fill="#3f4a6c")
  draw.line((0, 105, 255, 105), fill="#4b5678")
  draw.line((0, 106, 255, 106), fill="#3a4566")
  draw.rectangle((14, 84, 46, 116), fill="#232b44", outline="#485373")
  draw.ellipse((14, 79, 46, 89), fill="#2c3552", outline="#4d5878")
  draw.line((30, 79, 30, 70), fill="#465173", width=2)
  for y in range(88, 116, 7):
    draw.line((20, y, 26, y), fill="#1a2134")
  draw.line((148, 108, 168, 108), fill="#454f70")
  draw.rectangle((146, 108, 168, 116), fill="#242c45", outline="#454f70")
  draw.line((152, 111, 162, 111), fill="#39425f")
  draw.line((226, 116, 226, 42), fill="#39415d", width=2)
  draw.line((214, 56, 238, 56), fill="#39415d", width=2)
  draw.line((218, 47, 234, 47), fill="#39415d", width=2)
  draw.ellipse((118, 138, 176, 142), fill="#26314c")
  draw.rectangle((132, 139, 150, 139), fill="#8a92b4")
  for index in range(3):
    phase = (time*.5+index*.28) % 1
    x = int(244-phase*268)
    y = 30+index*17
    draw.line((x, y, x+13, y-2), fill="#39415f")
  hero_x = 82+int(progress*54) if scene.get("action") == "walk" else 108
  person(image, hero_x, 116, time, action=scene.get("action", "walk"),
         view=scene.get("hero_view", "right"), animation_fps=scene.get("_animation_fps", 8),
         sprites=scene.get("_sprite_assets"))
  return night_tint(image, scene.get("palette", "night"))


def crossing(scene, time):
  """Both sides of the street at once: he stands near, she stands far away."""
  local = time-scene["start"]
  span = max(.001, scene["end"]-scene["start"])
  progress = min(1, max(0, local/span))
  pan = int(round((progress-.5)*44))
  far = int(pan*.5)
  image = Image.new("RGBA", SIZE, "#0a1226")
  draw = ImageDraw.Draw(image)
  for y in range(50):
    blend = y/49
    color = tuple(round(a+(b-a)*blend) for a, b in zip((8, 13, 34), (38, 38, 68)))
    draw.line((0, y, 255, y), fill=color)
  draw.rectangle((0, 42, 255, 50), fill="#3b3350")
  draw.rectangle((0, 47, 255, 50), fill="#4a3d55")
  rng = random.Random(64)
  x = -80+far % 20
  while x < 330:
    width = rng.randint(13, 21)
    top = rng.randint(16, 44)
    draw.rectangle((x, top, x+width, 84), fill=rng.choice(("#1b2740", "#212d49", "#26324f")))
    for wy in range(top+5, 78, 7):
      for wx in range(x+3, x+width-2, 5):
        if rng.random() > .5:
          draw.rectangle((wx, wy, wx+1, wy+2), fill=rng.choice(("#f6dca1", "#f6dca1", "#496080")))
    x += width+rng.randint(2, 7)
  draw.rectangle((0, 84, 255, 90), fill="#2a3450")
  draw.line((0, 84, 255, 84), fill="#5f6a8b")
  draw.line((0, 90, 255, 90), fill="#151c2e")
  draw.rectangle((0, 91, 255, 116), fill="#121a2b")
  for y in (99, 107):
    draw.line((0, y, 255, y), fill="#171f33")
  for lamp_x in (26+pan, 222+pan):
    draw.rectangle((lamp_x-9, 91, lamp_x+9, 115), fill="#18213a")
    draw.rectangle((lamp_x-4, 92, lamp_x+4, 115), fill="#1d2742")
  draw.rectangle((0, 94, 255, 95), fill="#4b5670")
  for index in range(12):
    x0 = 2+index*22+pan
    draw.rectangle((x0, 103, x0+7, 104), fill="#39435c")
    draw.rectangle((x0+11, 110, x0+16, 111), fill="#39435c")
  draw.rectangle((0, 116, 255, 143), fill="#333d58")
  draw.line((0, 116, 255, 116), fill="#616c8d")
  draw.line((0, 117, 255, 117), fill="#242c42")
  for x in range(4, 256, 11):
    draw.point((x, 122), fill="#414c69")
    draw.point((x, 137), fill="#414c69")
  draw.line((160+far, 56, 160+far, 84), fill="#6a7391", width=2)
  draw.rectangle((156+far, 53, 164+far, 56), fill="#f0dda8")
  draw.ellipse((152+far, 56, 168+far, 62), fill="#3a3350")
  for pole_x in (26+pan, 222+pan):
    draw.line((pole_x, 44, pole_x, 116), fill="#8b93ad", width=2)
    draw.rectangle((pole_x-4, 41, pole_x+4, 44), fill="#5b6580")
    draw.rectangle((pole_x-3, 44, pole_x+3, 47), fill="#f8e8ba")
    draw.rectangle((pole_x-11, 116, pole_x+11, 128), fill="#3a4560")
    draw.rectangle((pole_x-4, 116, pole_x+4, 134), fill="#4c5674")
    draw.rectangle((pole_x-2, 119, pole_x+2, 131), fill="#6a7396")
  draw.line((244+pan, 40, 244+pan, 116), fill="#8b93ad", width=2)
  draw.rectangle((238+pan, 30, 250+pan, 50), fill="#242c44", outline="#8b93ad")
  green = progress > .6 and scene.get("signal", "auto") != "red"
  draw.ellipse((241+pan, 32, 247+pan, 38), fill="#3a2630" if green else "#e05a5a")
  draw.ellipse((241+pan, 41, 247+pan, 47), fill="#6fdc9c" if green else "#243a30")
  if scene.get("partner"):
    small_umbrella(draw, 188+far, 66, scene.get("far_umbrella", "pink"))
    tiny_person(image, 184+far, 90, time, partner=True, view=scene.get("partner_view", "left"))
    tiny_person(image, 194+far, 90, time, silhouette=True)
    draw.rectangle((180+far, 92, 200+far, 94), fill="#3a2f45")
  item = scene.get("umbrella")
  if item:
    umbrella(draw, 84, 84, item.get("color", "blue"))
  person(image, 84, 116, time, action=scene.get("action", "idle"),
         view=scene.get("hero_view", "left"), animation_fps=scene.get("_animation_fps", 8),
         sprites=scene.get("_sprite_assets"))
  density = rain_density(scene, progress)
  if density > 0.02:
    rain(image, time, density=density)
    rain(image, time, foreground=True, density=density)
  return night_tint(image, scene.get("palette", "night"))


def street_scene(scene, time):
  kind = scene["kind"]
  local = time-scene["start"]
  progress = min(1, max(0, local/(scene["end"]-scene["start"])))
  density = rain_density(scene, progress) if kind in ("rain_city", "bus_stop") else 0.0
  if kind in ("classroom", "bookstore"):
    image = interior(kind)
  else:
    image = city(time, wet=density > 0.02)
  if scene.get("background_image") is not None:
    image = scene["background_image"].copy()
  draw = ImageDraw.Draw(image)
  if density > 0.02:
    rain(image, time, density=density)
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
    draw.rectangle((0, 0, 255, 143), fill="#2f3b52")
    draw.rectangle((0, 0, 255, 6), fill="#3a4861")
    draw.rectangle((4, 7, 251, 57), fill="#0e1a30", outline="#8fa1b8", width=2)
    offset = int(time*24) % 64
    for index in range(-1, 6):
      bx = index*64-offset
      height = 12+(index*11) % 20
      draw.rectangle((bx+3, 57-height, bx+46, 57), fill="#0a1424")
      for wy in range(57-height+3, 54, 6):
        for wx in range(bx+7, bx+42, 8):
          if (wx+wy+index) % 3:
            draw.rectangle((wx, wy, wx+1, wy+2), fill="#f2d79b")
    for index in range(3):
      streak = int((index*97+time*46) % 288)-16
      draw.line((streak, 51, streak+11, 51), fill="#5d6f8a")
    for mullion in (88, 168):
      draw.rectangle((mullion, 7, mullion+3, 57), fill="#33415a")
    draw.rectangle((0, 57, 255, 63), fill="#3c4a63")
    draw.line((0, 66, 255, 66), fill="#c9a45c", width=2)
    for strap in (74, 104, 134, 164, 194):
      draw.line((strap, 66, strap, 72), fill="#c9a45c")
      draw.ellipse((strap-2, 72, strap+2, 76), outline="#c9a45c")
    draw.rectangle((0, 78, 255, 100), fill="#2c6f74")
    draw.line((0, 78, 255, 78), fill="#57a0a0")
    for seam in range(6, 256, 40):
      draw.line((seam, 80, seam, 99), fill="#245c62")
    draw.rectangle((0, 100, 255, 143), fill="#39415a")
    draw.line((0, 100, 255, 100), fill="#222a3d")
    for tile in range(0, 256, 24):
      draw.line((tile, 105, tile+12, 105), fill="#2f3750")
    animation_fps = scene.get("_animation_fps", 8)
    if scene.get("solo"):
      for x in (34, 66, 92):
        person(image, x, 116, time, silhouette=True, animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
      if scene.get("partner"):
        person(image, 150, 116, time, partner=True, view=scene.get("partner_view", "left"),
               animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
        person(image, 164, 116, time, silhouette=True, animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
      person(image, 224, 116, time, view=scene.get("hero_view", "back"), animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
    else:
      for x in (20, 65, 108, 155, 196, 236):
        partner = x in (65, 196)
        person(image, x, 116, time, partner=partner,
               view=scene.get("partner_view" if partner else "hero_view", "front"),
               animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
    for pole in (52, 200):
      draw.line((pole, 63, pole, 116), fill="#c9a45c", width=2)
  elif kind == "memory_items":
    draw.rectangle((0, 0, 255, 143), fill="#14213d")
    for index, color in enumerate(("#7e9bb8", "#d99bb5", "#a8b08b")):
      x = 42+index*62
      draw.rectangle((x, 40, x+44, 92), outline="#92a3bc", width=2)
      inventory = scene.get("_state", {}).get("inventory", [])
      draw.rectangle((x+8, 47, x+36, 80), fill="#1b2a49", outline="#40536f")
      if index < len(inventory):
        item_icon(draw, inventory[index], x+22, 64, color)
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
    item = scene.get("umbrella")
    if item:
      owner = item.get("owner", "shared")
      center = hero_x if owner == "hero" else hero_x+26 if owner == "partner" else hero_x+13
      umbrella(draw, center, 81, item.get("color", "blue"))
    person(image, hero_x, 113, time, action=scene.get("action", "idle"),
           view=scene.get("hero_view", "front"), animation_fps=animation_fps,
           sprites=scene.get("_sprite_assets"))
    if scene.get("partner"):
      person(image, hero_x+26, 113, time, partner=True, view=scene.get("partner_view", "front"),
             animation_fps=animation_fps, sprites=scene.get("_sprite_assets"))
    if scene.get("partner") and kind in ("rain_city", "bus_stop"):
      heart(draw, hero_x+16, 72-int(math.sin(time*2)*2), color="#f0a8bd")
  if density > 0.02:
    rain(image, time, foreground=True, density=density)
  return night_tint(image, scene.get("palette", "night"))


SCENES = {"rooftop": rooftop, "crossing": crossing}



def item_icon(draw, name, cx, cy, color):
  """Small collectible icons so the three memories stay distinguishable after the filter."""
  edge = "#efe6cf"
  if "纸鹤" in name:
    draw.polygon([(cx-9, cy+4), (cx-6, cy-3), (cx+9, cy-6), (cx+2, cy+2)], fill=color, outline=edge)
    draw.polygon([(cx+2, cy+2), (cx+9, cy-6), (cx+7, cy+8), (cx-2, cy+4)], fill=color, outline=edge)
    draw.line((cx+9, cy-6, cx+12, cy-9), fill=edge)
  elif "汽水" in name:
    draw.rectangle((cx-5, cy-2, cx+5, cy+9), fill=color, outline=edge)
    draw.rectangle((cx-2, cy-9, cx+2, cy-2), fill=color, outline=edge)
    draw.rectangle((cx-3, cy-11, cx+3, cy-9), fill="#e6dcc2")
    draw.line((cx-2, cy+1, cx-2, cy+7), fill="#f5eed7")
  elif "磁带" in name:
    draw.rectangle((cx-11, cy-7, cx+11, cy+7), fill="#2f3446", outline=edge)
    draw.rectangle((cx-8, cy-5, cx+8, cy-1), fill=color, outline="#c9c0aa")
    draw.ellipse((cx-6, cy+1, cx-1, cy+6), fill="#e4dec7")
    draw.ellipse((cx+1, cy+1, cx+6, cy+6), fill="#e4dec7")
    draw.rectangle((cx-4, cy+4, cx+4, cy+6), fill="#171d2c")
  elif "信" in name:
    draw.rectangle((cx-9, cy-6, cx+9, cy+7), fill=color, outline=edge)
    draw.line((cx-9, cy-6, cx, cy+1), fill=edge)
    draw.line((cx+9, cy-6, cx, cy+1), fill=edge)
  elif "伞" in name:
    draw.polygon([(cx-10, cy), (cx-5, cy-8), (cx+5, cy-8), (cx+10, cy)], fill=color, outline=edge)
    draw.line((cx, cy-8, cx, cy+8), fill=edge)
  else:
    draw.rectangle((cx-9, cy-9, cx+9, cy+9), fill=color, outline=edge)


def render_rain_scene(scene, time):
  image = SCENES.get(scene["kind"], street_scene)(scene, time)
  if scene.get("narrative_time") == "memory" and scene.get("memory_filter", True):
    image = ImageOps.colorize(image.convert("RGB").convert("L"), "#5f4a3d", "#f3e2bf").convert("RGBA")
  return image
