"""Pixel-aligned scene compositor: images, sprites, keyframes and parallax."""
import math
from pathlib import Path
from PIL import Image, ImageColor
from narrative_events import scroll_position


def finite(value):
  return type(value) in (int, float) and math.isfinite(value)


def prepare(scene, base, sprites, canvas):
  if scene.get('background'):
    raise ValueError('composite 请将背景作为 image 图层配置。')
  layers = scene.get('layers')
  if not isinstance(layers, list) or not layers:
    raise ValueError('composite 场景需要非空 layers 列表。')
  ImageColor.getrgb(scene.get('background_color', '#10182b'))
  ids = set()
  for layer in layers:
    if not isinstance(layer, dict) or not isinstance(layer.get('id'), str) or not layer['id'] or layer['id'] in ids:
      raise ValueError('每个图层需要唯一非空 id。')
    ids.add(layer['id'])
    if layer.get('type') not in ('image', 'sprite') or type(layer.get('z', 0)) is not int:
      raise ValueError('图层 type 必须为 image/sprite，z 必须为整数。')
    for key, default in (('x', 0), ('y', 0), ('opacity', 1), ('parallax', 1)):
      if not finite(layer.get(key, default)):
        raise ValueError('图层位置、透明度和视差必须为有限数。')
    if not 0 <= layer.get('opacity', 1) <= 1 or type(layer.get('repeat_x', False)) is not bool:
      raise ValueError('图层透明度需在 0–1 之间，repeat_x 必须为布尔值。')
    zoom = layer.get('scale', 1)
    if type(zoom) is not int or not 1 <= zoom <= 8:
      raise ValueError('图层 scale 必须为 1–8 的整数。')
    start, end = layer.get('start', scene['start']), layer.get('end', scene['end'])
    if not finite(start) or not finite(end) or not scene['start'] <= start < end <= scene['end']:
      raise ValueError('图层 start/end 必须位于场景时间内。')
    layer['_start'] = start
    if not isinstance(layer.get('keyframes', []), list):
      raise ValueError('keyframes 必须是列表。')
    last = -1
    for keyframe in layer.get('keyframes', []):
      if (not isinstance(keyframe, dict) or set(keyframe) - {'time', 'x', 'y', 'opacity'} or
          not finite(keyframe.get('time')) or not scene['start'] <= keyframe['time'] <= scene['end'] or
          keyframe['time'] <= last):
        raise ValueError('关键帧必须按绝对时间递增，且仅包含 time/x/y/opacity。')
      for key in ('x', 'y', 'opacity'):
        if key in keyframe and (not finite(keyframe[key]) or (key == 'opacity' and not 0 <= keyframe[key] <= 1)):
          raise ValueError('关键帧位置或透明度无效。')
      last = keyframe['time']
    if layer['type'] == 'image':
      with Image.open(Path(base) / layer['file']) as source:
        layer['_image'] = source.convert('RGBA')
    else:
      name = layer.get('actor')
      if not isinstance(name, str) or not sprites.has(name):
        raise ValueError('图层引用了未配置的精灵角色：{}'.format(name))
      if layer.get('repeat_x', False):
        raise ValueError('sprite 图层不支持 repeat_x。')
      sprites.frame(name, layer.get('action', 'idle'), layer.get('view', 'front'), 0)
  scene['_canvas'], scene['_sprites'] = canvas, sprites


def value_at(layer, key, time, default):
  points = [(layer['_start'], layer.get(key, default))]
  points.extend((frame['time'], frame[key]) for frame in layer.get('keyframes', []) if key in frame)
  points.sort(key=lambda point: point[0])
  for index, (t, value) in enumerate(points):
    if time < t:
      if index == 0:
        return value
      prev_t, prev_value = points[index-1]
      if t == prev_t:
        return value
      ratio = (time-prev_t)/(t-prev_t)
      return prev_value + (value-prev_value)*ratio
  return points[-1][1]


def render(scene, time):
  image = Image.new('RGBA', tuple(scene['_canvas']), scene.get('background_color', '#10182b'))
  camera = scroll_position(scene, time)
  for layer in sorted(scene['layers'], key=lambda item: item.get('z', 0)):
    if not layer.get('start', scene['start']) <= time < layer.get('end', scene['end']):
      continue
    x = value_at(layer, 'x', time, 0) - camera * layer.get('parallax', 1)
    y = value_at(layer, 'y', time, 0)
    opacity = value_at(layer, 'opacity', time, 1)
    zoom = layer.get('scale', 1)
    if layer['type'] == 'sprite':
      frame, anchor = scene['_sprites'].frame(layer['actor'], layer.get('action', 'idle'),
                                               layer.get('view', 'front'), time-scene['start'])
      x -= anchor[0]*zoom
      y -= anchor[1]*zoom
    else:
      frame = layer['_image']
    if zoom != 1:
      frame = frame.resize((frame.width*zoom, frame.height*zoom), Image.Resampling.NEAREST)
    if opacity < 1:
      frame = frame.copy()
      frame.putalpha(frame.getchannel('A').point(lambda alpha: round(alpha*opacity)))
    x, y = round(x), round(y)
    if layer.get('repeat_x', False):
      x = x % frame.width - frame.width
      while x < image.width:
        image.alpha_composite(frame, (x, y))
        x += frame.width
    else:
      image.alpha_composite(frame, (x, y))
  return image
