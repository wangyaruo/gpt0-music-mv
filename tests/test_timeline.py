import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from render_mv import karaoke_states,layout_glyphs,parse_lrc,validate,wrap_text
from PIL import ImageFont


class TimelineTests(unittest.TestCase):
  def setUp(self):
    self.config = json.loads((ROOT/"examples/demo.json").read_text(encoding="utf-8"))

  def test_example_is_contiguous(self):
    validate(self.config)

  def test_gap_overlap_and_nonfinite_are_rejected(self):
    for value in (1.5,2.5,float("nan")):
      config = copy.deepcopy(self.config)
      config["scenes"][1]["start"] = value
      with self.assertRaises(ValueError):
        validate(config)

  def test_state_cannot_reset(self):
    self.config["scenes"][-1]["coins"] = 0
    with self.assertRaises(ValueError):
      validate(self.config)

  def test_coins_may_decrease_for_an_explained_event(self):
    self.config["scenes"][-1]["coins"] = 0
    self.config["scenes"][-1]["event"] = "使用金币兑换奖励"
    validate(self.config)
    self.assertEqual(self.config["scenes"][-1]["coins"], 0)

  def test_lrc_offset_multitimestamp_and_blank_pause(self):
    result = parse_lrc("[ar:demo]\n[offset:100]\n[00:00.00][00:02.00]海风\n[00:04.00]\n[00:05.00]出发",7)
    self.assertEqual([row["start"] for row in result],[.1,2.1,5.1])
    self.assertEqual(result[1]["end"],4.1)
    self.assertEqual(result[-1]["end"],7)

  def test_duplicate_lrc_and_invalid_seconds_are_rejected(self):
    for text in ("[00:01.00]a\n[00:01.00]b","[00:65.00]bad","[00:09.00]late"):
      with self.assertRaises(ValueError):
        parse_lrc(text,8)

  def test_wrapping_keeps_every_character(self):
    text = "a readable sentence"
    lines = wrap_text(text,ImageFont.load_default(),40)
    self.assertEqual("".join(lines),text)
    self.assertGreater(len(lines),1)

  def test_rain_example_keeps_time_branches_separate(self):
    config = json.loads((ROOT/"examples/rain-demo.json").read_text(encoding="utf-8"))
    validate(config)
    self.assertEqual(config["scenes"][3]["_state"]["inventory"], ["旧书"])
    self.assertEqual(config["scenes"][4]["_state"]["inventory"], ["旧书", "雨伞"])
    self.assertEqual(config["scenes"][5]["_state"]["inventory"], ["信笺"])
    self.assertEqual(config["scenes"][5]["_state"]["party"], ["hero", "partner"])
    self.assertEqual(config["scenes"][7]["_state"]["inventory"], ["雨伞"])

  def test_state_change_requires_reason(self):
    config = json.loads((ROOT/"examples/rain-demo.json").read_text(encoding="utf-8"))
    del config["scenes"][2]["event"]
    with self.assertRaises(ValueError):
      validate(config)

  def test_partner_may_be_visible_after_leaving_party(self):
    config = json.loads((ROOT/"examples/rain-demo.json").read_text(encoding="utf-8"))
    config["scenes"][1]["partner"] = True
    validate(config)
    self.assertEqual(config["scenes"][1]["_state"]["party"], ["hero"])
    self.assertTrue(config["scenes"][1]["partner"])

  def test_scene_options_never_silently_ignore_unsupported_effects(self):
    for change in (lambda scene: scene.update(partner="false"),
                   lambda scene: scene.update(weather="rain"),
                   lambda scene: scene.update(bus="approach")):
      config = copy.deepcopy(self.config)
      change(config["scenes"][1])  # A beach scene does not implement rain or bus effects.
      with self.assertRaises(ValueError):
        validate(config)

  def test_karaoke_token_timing_and_approximate_fallback(self):
    line = {"start": 0, "end": 2, "text": "下雨了", "tokens": [
      {"text": "下雨", "start": 0, "end": 1}, {"text": "了", "start": 1, "end": 2}]}
    self.assertEqual(karaoke_states(line, .5), ["active", "active", "pending"])
    self.assertEqual(karaoke_states(line, 1.5), ["played", "played", "active"])
    del line["tokens"]
    self.assertEqual(karaoke_states(line, .8), ["played", "active", "pending"])
    self.assertEqual(karaoke_states(line, -1), ["pending", "pending", "pending"])
    self.assertEqual(karaoke_states(line, 2), ["played", "played", "played"])

  def test_bad_token_text_and_time_are_rejected(self):
    config = json.loads((ROOT/"examples/rain-demo.json").read_text(encoding="utf-8"))
    for change in (lambda row: row["tokens"][0].update(text="错误"),
                   lambda row: row["tokens"][1].update(start=.2)):
      candidate = copy.deepcopy(config)
      change(candidate["lyrics"][0])
      with self.assertRaises(ValueError):
        validate(candidate)

  def test_glyph_indices_survive_explicit_newlines(self):
    layout = layout_glyphs("AB\nCD", ImageFont.load_default(), 100)
    self.assertEqual(layout, [[(0,"A"),(1,"B")],[(3,"C"),(4,"D")]])


if __name__ == "__main__":
  unittest.main()
