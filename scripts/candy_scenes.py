"""Original side-scrolling candy-world pixel art and non-destructive visual cut-ins."""
import math
from PIL import Image, ImageDraw, ImageOps
from narrative_events import scroll_position
from pixel_world import SIZE, heart, person


def candy_background(scene, time):
  palette = scene.get("palette", "day")
  if palette == "night":
    sky, hills, hills2 = "#192449", "#654c78", "#8b6087"
  elif palette == "sunset":
    sky, hills, hills2 = "#d67780", "#d99a9d", "#a36580"
  else:
    sky, hills, hills2 = "#78c9dc", "#f8c6bd", "#f5a8b7"
  image = Image.new("RGBA", SIZE, sky)
  draw = ImageDraw.Draw(image)
  offset = scroll_position(scene, time)
  for y in range(0, 66, 5):
    draw.line((0, y, 255, y), fill="#a9dce4" if palette == "day" and y > 32 else sky)
  for x in range(-70, 330, 65):
    left = int(x-(offset*.12 % 65))
    draw.ellipse((left, 52, left+74, 104), fill=hills)
    draw.ellipse((left+17, 60, left+88, 106), fill=hills2)
  for x in range(-80, 330, 88):
    left = int(x-(offset*.3 % 88))
    draw.rectangle((left+8, 69, left+58, 102), fill="#f2ddc4", outline="#c98793")
    draw.rectangle((left+4, 67, left+62, 72), fill="#dd9fa8")
    for window in range(4):
      draw.rectangle((left+14+window*10, 77, left+19+window*10, 88), fill="#f8c79d")
  colors = ("#e47a97", "#79c3ce", "#f3c668", "#a5c788", "#c292c8")
  pole_offset = offset*.62
  base_index = math.floor(pole_offset/40)
  for position in range(-1, 8):
    x = int(position*40-pole_offset%40)
    index = position+base_index
    draw.line((x, 75, x, 105), fill="#f5e4d5", width=2)
    color = colors[index%len(colors)]
    draw.ellipse((x-7, 69, x+7, 83), fill=color, outline="#fff3dd")
    draw.line((x-4, 74, x+4, 79), fill="#fff3dd")
    draw.line((x-4, 79, x+4, 74), fill="#fff3dd")
  draw.rectangle((0, 101, 255, 112), fill="#ca8d77")
  draw.line((0, 102, 255, 102), fill="#fff3d8")
  for x in range(-20, 280, 18):
    post = int(x-offset%18)
    draw.rectangle((post, 103, post+3, 111), fill="#f9e3cb")
    draw.rectangle((post, 105, post+3, 106), fill="#cf6c7c")
    draw.rectangle((post, 109, post+3, 110), fill="#cf6c7c")
  draw.rectangle((0, 112, 255, 143), fill="#ad8170")
  for x in range(-24, 280, 24):
    xx = int(x-offset%24)
    draw.line((xx, 113, xx, 143), fill="#986d61")
  for y in (119, 129, 139):
    draw.line((0, y, 255, y), fill="#c6977f")
  return image


def eyes_cutin(actor):
  image = Image.new("RGBA", SIZE, "#f6c8a7")
  draw = ImageDraw.Draw(image)
  hair = "#754650" if actor == "partner" else "#242a3d"
  draw.rectangle((0, 0, 255, 25), fill=hair)
  draw.polygon([(0, 24), (49, 21), (71, 30), (105, 21), (142, 29), (184, 20), (218, 28), (255, 22),
                (255, 0), (0, 0)], fill=hair)
  for x in (66, 190):
    draw.ellipse((x-25, 40, x+25, 90), fill="#fff7ed", outline=hair, width=3)
    draw.ellipse((x-15, 46, x+15, 85), fill="#6d4450", outline="#252a3d", width=2)
    draw.ellipse((x-7, 52, x+7, 76), fill="#202a3a")
    draw.rectangle((x+2, 54, x+6, 59), fill="#fffaf4")
    draw.rectangle((x-7, 68, x-4, 71), fill="#f3d3b0")
  draw.ellipse((18, 96, 65, 108), fill="#e9a49e")
  draw.ellipse((190, 96, 237, 108), fill="#e9a49e")
  return image


def render_candy_scene(scene, time):
  active = [event for event in scene.get("events", []) if event["start"] <= time < event["end"]]
  closeup = next((event for event in active if event["kind"] == "cutin"), None)
  if closeup:
    image = eyes_cutin(closeup.get("actor", "hero"))
  else:
    image = scene["background_image"].copy() if scene.get("background_image") is not None else candy_background(scene,time)
    person(image, 105, 110, time, action=scene.get("action", "walk"),
           view=scene.get("hero_view", "front"), animation_fps=scene.get("_animation_fps", 8))
    if scene.get("partner"):
      person(image, 138, 110, time, partner=True, action=scene.get("action", "walk"),
             view=scene.get("partner_view", "front"), animation_fps=scene.get("_animation_fps", 8))
    draw = ImageDraw.Draw(image)
    for event in active:
      if event["kind"] == "pickup":
        phase = (time-event["start"])/(event["end"]-event["start"])
        x, y = 124+int(phase*20), 74-int(phase*18)
        draw.ellipse((x-4,y-4,x+4,y+4),fill="#ffda6f",outline="#b56f76")
        draw.rectangle((x-7,y-1,x-5,y+1),fill="#f5b0c4")
        draw.rectangle((x+5,y-1,x+7,y+1),fill="#f5b0c4")
  draw = ImageDraw.Draw(image)
  for index in range(3):
    heart(draw, 8+index*9, 7)
  draw.rectangle((40,7,44,12),fill="#ffdf63",outline="#8a6a46")
  if scene.get("narrative_time") == "memory" and scene.get("memory_filter", True):
    image = ImageOps.colorize(image.convert("RGB").convert("L"),"#5f4a3d","#f3e2bf").convert("RGBA")
  return image
