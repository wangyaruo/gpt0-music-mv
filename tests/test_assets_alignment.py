import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from align_lyrics import align
from layer_compositor import prepare, render as render_layers
from render_mv import find_font, render, validate
from sprite_assets import SpritePack


class AlignmentTests(unittest.TestCase):
  def test_punctuation_and_repeated_chorus_keep_exact_text_and_word_times(self):
    words = [{'word': c, 'start': i, 'end': i + .8} for i, c in enumerate('下雨了下雨了')]
    result = align(['下雨了！', '下雨了？'], {'segments': [{'words': words}]})
    self.assertEqual([row['start'] for row in result['lyrics']], [0, 3])
    self.assertEqual([''.join(t['text'] for t in row['tokens']) for row in result['lyrics']],
                     ['下雨了！', '下雨了？'])
    self.assertTrue(all(row['status'] == 'draft' for row in result['lyrics']))
    self.assertEqual(result['lyrics'][0]['tokens'][-1]['end'], 2.8)

  def test_unmatched_text_and_cross_line_word_require_review(self):
    data = {'segments': [{'words': [{'word': '雨天', 'start': 1, 'end': 2}]}]}
    result = align(['雨', '天', '晴'], data)
    self.assertTrue(all(row['status'] == 'review_required' and row['start'] is None for row in result['lyrics']))

  def test_invalid_or_missing_timestamps_are_rejected(self):
    for words in ([], [{'word': '雨'}], [{'word': '雨', 'start': 1, 'end': 2},
                 {'word': '天', 'start': 1.5, 'end': 3}]):
      with self.assertRaises(ValueError):
        align(['雨天'], {'segments': [{'words': words}]})


class AssetTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.root = Path(self.temp.name)
    atlas = Image.new('RGBA', (4, 2))
    for x in range(2):
      for y in range(2):
        atlas.putpixel((x, y), (255, 0, 0, 255))
        atlas.putpixel((x+2, y), (0, 255, 0, 255))
    atlas.save(self.root/'atlas.png')
    self.spec = {'hero': {'image': 'atlas.png', 'frame_width': 2, 'frame_height': 2, 'anchor': [1, 2],
                          'animations': {'walk': {'front': {'frames': [0, 1], 'fps': 2}}}}}
    self.pack = SpritePack(self.spec, self.root)

  def tearDown(self):
    self.temp.cleanup()

  def test_atlas_frame_loop_and_invalid_animation(self):
    self.assertEqual(self.pack.frame('hero', 'walk', 'front', .6)[0].getpixel((0, 0)), (0, 255, 0, 255))
    self.assertEqual(self.pack.frame('hero', 'walk', 'front', 1.1)[0].getpixel((0, 0)), (255, 0, 0, 255))
    with self.assertRaises(ValueError):
      self.pack.frame('hero', 'idle', 'back', 0)

  def test_z_order_anchor_keyframes_and_camera(self):
    Image.new('RGBA', (2, 2), 'blue').save(self.root/'blue.png')
    scene = {'kind': 'composite', 'start': 0, 'end': 2, '_scroll_start': 0, '_scroll_speed': 1,
             'layers': [
               {'id': 'blue', 'type': 'image', 'file': 'blue.png', 'z': 0, 'x': 5, 'y': 5, 'parallax': 0},
               {'id': 'actor', 'type': 'sprite', 'actor': 'hero', 'action': 'walk', 'z': 1,
                'x': 5, 'y': 7, 'parallax': 0, 'keyframes': [{'time': 0, 'x': 5}, {'time': 2, 'x': 9}]}]}
    prepare(scene, self.root, self.pack, [20, 20])
    first, later = render_layers(scene, 0), render_layers(scene, 1)
    self.assertEqual(first.getpixel((5, 5)), (255, 0, 0, 255))
    self.assertEqual(later.getpixel((5, 5)), (0, 0, 255, 255))
    self.assertEqual(later.getpixel((7, 5)), (255, 0, 0, 255))

  def test_unknown_actor_and_bad_frames_are_rejected(self):
    broken = copy.deepcopy(self.spec)
    broken['hero']['animations']['walk']['front']['frames'] = [9]
    with self.assertRaises(ValueError):
      SpritePack(broken, self.root)
    scene = {'start': 0, 'end': 2, 'layers': [{'id': 'a', 'type': 'sprite', 'actor': 'missing'}]}
    with self.assertRaises(ValueError):
      prepare(scene, self.root, self.pack, [20, 20])

  def test_demo_still_and_unresolved_json(self):
    out = self.root/'preview.png'
    render(ROOT/'examples/composite-demo.json', out, font=find_font(), still=2)
    with Image.open(out) as image:
      self.assertEqual(image.size, (1280, 720))
    timeline = self.root/'lyrics.json'
    timeline.write_text(json.dumps({'lyrics': [{'text': '雨', 'start': None, 'end': None,
                                                'status': 'review_required'}]}), encoding='utf-8')
    with self.assertRaisesRegex(ValueError, '待处理'):
      render(ROOT/'examples/composite-demo.json', self.root/'bad.png', lyrics=timeline, font=find_font(), still=2)

  def test_non_composite_large_canvas_is_rejected(self):
    config = json.loads((ROOT/'examples/demo.json').read_text(encoding='utf-8'))
    config['canvas'] = [320, 180]
    with self.assertRaisesRegex(ValueError, 'composite'):
      validate(config)


if __name__ == '__main__':
  unittest.main()
