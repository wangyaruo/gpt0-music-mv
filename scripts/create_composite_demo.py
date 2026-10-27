#!/usr/bin/env python3
"""Create small original PNG assets for the layered demonstration."""
from pathlib import Path
from PIL import Image, ImageDraw
from pixel_world import sprite

root = Path(__file__).resolve().parent.parent / 'examples' / 'assets'
root.mkdir(parents=True, exist_ok=True)
background = Image.new('RGBA', (320, 180), '#a4cbd4')
d = ImageDraw.Draw(background)
d.rectangle((0, 82, 320, 180), fill='#bed9cf')
d.ellipse((238, 18, 276, 56), fill='#fbe5ab')
for x, y in ((24, 24), (110, 40), (190, 19)):
  d.rectangle((x, y, x+40, y+8), fill='#ecf0dd')
  d.rectangle((x+8, y-5, x+30, y+4), fill='#ecf0dd')
background.save(root / 'sky.png')
city = Image.new('RGBA', (160, 180))
d = ImageDraw.Draw(city)
for x, height, color in ((0, 53, '#819faa'), (38, 70, '#77969f'), (90, 44, '#91aab0'), (125, 61, '#728f9d')):
  d.rectangle((x, 132-height, x+30, 132), fill=color)
  for xx in range(x+5, x+25, 8):
    for yy in range(138-height, 120, 12):
      d.rectangle((xx, yy, xx+3, yy+5), fill='#e9dbb3')
city.save(root / 'city.png')
ground = Image.new('RGBA', (80, 180))
d = ImageDraw.Draw(ground)
d.rectangle((0, 128, 80, 179), fill='#696e78')
d.rectangle((0, 128, 80, 131), fill='#d6c2a1')
for x in range(0, 80, 20):
  d.line((x, 147, x+10, 147), fill='#cabda9', width=2)
ground.save(root / 'ground.png')
sheet = Image.new('RGBA', (48, 19))
for index in range(4):
  sheet.alpha_composite(sprite(step=index % 2), (index*12, 0))
sheet.save(root / 'hero.png')
print('Created original example PNG assets in', root)
