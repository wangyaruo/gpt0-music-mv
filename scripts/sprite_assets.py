"""Load user-supplied PNG sprite atlases once, preserving their pixel grid."""
import math
from pathlib import Path
from PIL import Image


class SpritePack:
  def __init__(self, definitions, base):
    if not isinstance(definitions, dict):
      raise ValueError('sprites 必须是以角色名为键的对象。')
    self.actors = {}
    for name, spec in definitions.items():
      if not isinstance(name, str) or not name or not isinstance(spec, dict):
        raise ValueError('sprites 角色名和配置无效。')
      w, h = spec.get('frame_width'), spec.get('frame_height')
      if type(w) is not int or type(h) is not int or w < 1 or h < 1:
        raise ValueError('精灵帧宽和帧高必须为正整数。')
      with Image.open(Path(base) / spec['image']) as source:
        sheet = source.convert('RGBA')
      if sheet.width % w or sheet.height % h:
        raise ValueError('精灵图尺寸必须能被帧尺寸整除。')
      anchor = spec.get('anchor', [w // 2, h])
      if (not isinstance(anchor, list) or len(anchor) != 2 or
          any(type(n) is not int for n in anchor) or not 0 <= anchor[0] <= w or not 0 <= anchor[1] <= h):
        raise ValueError('精灵 anchor 必须位于帧内或边界上。')
      count = (sheet.width // w) * (sheet.height // h)
      frames = [sheet.crop(((i % (sheet.width // w))*w, (i // (sheet.width // w))*h,
                            (i % (sheet.width // w)+1)*w, (i // (sheet.width // w)+1)*h))
                for i in range(count)]
      animations = spec.get('animations')
      if not isinstance(animations, dict) or not animations:
        raise ValueError('精灵必须配置 animations。')
      for action, views in animations.items():
        if not isinstance(views, dict) or not views:
          raise ValueError('动画必须按视角配置。')
        for view, anim in views.items():
          if not isinstance(anim, dict):
            raise ValueError('动画配置必须是对象。')
          indices, fps, loop = anim.get('frames'), anim.get('fps', 8), anim.get('loop', True)
          if (not isinstance(indices, list) or not indices or
              any(type(i) is not int or not 0 <= i < count for i in indices) or
              type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0 or type(loop) is not bool):
            raise ValueError('动画帧索引、fps 或 loop 无效。')
      portrait = None
      if spec.get('portrait'):
        with Image.open(Path(base) / spec['portrait']) as source:
          portrait = source.convert('RGBA')
      self.actors[name] = {'frames': frames, 'anchor': anchor, 'animations': animations, 'portrait': portrait}

  def has(self, name):
    return name in self.actors

  def portrait(self, name):
    actor = self.actors[name]
    if actor['portrait'] is not None:
      return actor['portrait']
    frame = actor['frames'][0]
    return frame.crop((0, 0, frame.width, max(1, frame.height * 3 // 5)))

  def frame(self, name, action, view, time):
    actor = self.actors[name]
    try:
      anim = actor['animations'][action][view]
    except KeyError:
      raise ValueError('角色 {} 缺少 {} / {} 动画。'.format(name, action, view)) from None
    tick = max(0, int(time * anim.get('fps', 8)))
    indices = anim['frames']
    index = tick % len(indices) if anim.get('loop', True) else min(tick, len(indices)-1)
    return actor['frames'][indices[index]], actor['anchor']
