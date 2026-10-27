import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"scripts"))
from narrative_events import scroll_position, state_at
from render_mv import lyric_color, validate


class EventTests(unittest.TestCase):
  def setUp(self):
    self.config = json.loads((ROOT/"examples/candy-demo.json").read_text(encoding="utf-8"))

  def test_pickup_applies_only_after_completion_and_survives_next_scene(self):
    validate(self.config)
    first, second = self.config["scenes"][:2]
    before, before_coins = state_at(first, 1.99)
    after, after_coins = state_at(first, 2)
    self.assertEqual((before["inventory"], before_coins), ([], 0))
    self.assertEqual((after["inventory"], after_coins), (["糖果"], 1))
    self.assertEqual(second["_state"]["inventory"], ["糖果"])
    self.assertEqual(second["coins"], 1)
    # Frame requests can arrive out of order without mutating the initial snapshot.
    self.assertEqual(state_at(first, 1)[0]["inventory"], [])

  def test_meter_interpolates_and_restores_previous_value_at_next_scene(self):
    validate(self.config)
    first, second, third = self.config["scenes"][:3]
    self.assertEqual(state_at(first, 1)[0]["gauges"]["温暖"], 10)
    self.assertEqual(state_at(first, 3)[0]["gauges"]["温暖"], 22.5)
    self.assertEqual(second["_state"]["gauges"]["温暖"], 35)
    self.assertEqual(third["_state"]["gauges"]["温暖"], 65)

  def test_camera_continues_across_scenes_and_fast_forward(self):
    validate(self.config)
    first, second, third, fourth = self.config["scenes"][:4]
    self.assertAlmostEqual(scroll_position(first, 6), scroll_position(second, 6))
    self.assertAlmostEqual(scroll_position(second, 12), scroll_position(third, 12))
    self.assertAlmostEqual(scroll_position(third, 16), 171.2)
    self.assertAlmostEqual(scroll_position(third, 18), scroll_position(fourth, 18))
    self.assertAlmostEqual(scroll_position(fourth, 19)-scroll_position(fourth, 18), 5)

  def test_camera_and_gauges_do_not_leak_between_story_branches(self):
    self.config["scenes"][2]["narrative_time"] = "memory"
    validate(self.config)
    memory, present = self.config["scenes"][2:4]
    self.assertEqual(memory["_scroll_start"], 0)
    self.assertEqual(present["_scroll_start"], 96)
    self.assertEqual(present["_state"]["gauges"]["温暖"], 65)

  def test_overlapping_pickups_are_recorded_by_completion_time(self):
    self.config["scenes"][0]["events"] = [
      {"kind":"pickup", "start":.2, "end":4, "item":"甲", "coins":1},
      {"kind":"pickup", "start":1, "end":2, "item":"乙", "coins":1}]
    validate(self.config)
    first, second = self.config["scenes"][:2]
    self.assertEqual(state_at(first, 2)[0]["inventory"], ["乙"])
    self.assertEqual(state_at(first, 4)[0]["inventory"], ["乙", "甲"])
    self.assertEqual(second["_state"]["inventory"], ["乙", "甲"])

  def test_highlight_color_has_lower_priority_than_active_karaoke(self):
    lyric = {"text":"糖果", "highlights":[{"start":0,"end":2,"color":"#ffc75a"}]}
    self.assertEqual(lyric_color(lyric, 0, "played"), "#ffc75a")
    self.assertEqual(lyric_color(lyric, 0, "active"), "#ff9dc0")
    self.assertEqual(lyric_color(lyric, 0, "pending"), "#7e87a2")

  def test_rejects_mismatched_meter_and_out_of_scene_events(self):
    candidate = copy.deepcopy(self.config)
    candidate["scenes"][1]["events"][2]["from"] = 80
    with self.assertRaises(ValueError):
      validate(candidate)
    candidate = copy.deepcopy(self.config)
    candidate["scenes"][0]["events"][0]["end"] = 7
    with self.assertRaises(ValueError):
      validate(candidate)

  def test_rejects_overlapping_highlights_and_ambiguous_fast_forward(self):
    candidate = copy.deepcopy(self.config)
    candidate["lyrics"][0]["highlights"].append({"start":6,"end":8,"color":"#ffffff"})
    with self.assertRaises(ValueError):
      validate(candidate)
    candidate = copy.deepcopy(self.config)
    candidate["scenes"][2]["events"].append({"kind":"fast_forward","start":15,"end":16.5,"factor":3})
    with self.assertRaises(ValueError):
      validate(candidate)


if __name__ == "__main__":
  unittest.main()
