import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from render_mv import parse_lrc,validate,wrap_text
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


if __name__ == "__main__":
  unittest.main()
