import json
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"scripts"))
from media_utils import ffmpeg_path, probe
from render_mv import find_font, render


class RenderIntegrationTests(unittest.TestCase):
  def setUp(self):
    try:
      self.ffmpeg = ffmpeg_path()
      self.font = find_font()
    except ValueError as error:
      self.skipTest(str(error))
    self.temp = tempfile.TemporaryDirectory()
    self.root = Path(self.temp.name)
    config = json.loads((ROOT/"examples/rain-demo.json").read_text(encoding="utf-8"))
    config["duration"] = 2
    config["scenes"] = config["scenes"][:1]
    config["scenes"][0]["end"] = 2
    config["scale"] = 2
    config["lyrics"] = [{"start": 0, "end": 2, "text": "雨夜", "timing_source": "manual", "tokens": [
      {"text": "雨", "start": 0, "end": 1}, {"text": "夜", "start": 1, "end": 2}]}]
    self.story = self.root/"story.json"
    self.story.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

  def tearDown(self):
    if hasattr(self, "temp"):
      self.temp.cleanup()

  def tone(self, seconds):
    path = self.root/"tone.wav"
    with wave.open(str(path), "wb") as stream:
      stream.setnchannels(1)
      stream.setsampwidth(2)
      stream.setframerate(16000)
      stream.writeframes(b"".join(struct.pack("<h", int(500*math.sin(2*math.pi*440*i/16000)))
                                  for i in range(int(16000*seconds))))
    return path

  def test_audio_mux_and_karaoke_metadata(self):
    output = self.root/"video.mp4"
    result = render(self.story, output, audio=self.tone(2), font=self.font, ffmpeg=self.ffmpeg)
    actual = probe(output, self.ffmpeg)
    self.assertTrue(actual["has_audio"])
    self.assertEqual((actual["width"], actual["height"], actual["fps"]), (512, 288, 12))
    self.assertAlmostEqual(actual["duration"], 2, places=1)
    self.assertEqual(result["subtitle_timing"]["word_timed_lines"], 1)
    self.assertEqual(result["subtitle_timing"]["declared_sources"]["manual"], 1)

  def test_short_audio_does_not_replace_existing_file(self):
    output = self.root/"existing.mp4"
    output.write_bytes(b"existing user data")
    with self.assertRaises(ValueError):
      render(self.story, output, audio=self.tone(1), font=self.font, ffmpeg=self.ffmpeg, overwrite=True)
    self.assertEqual(output.read_bytes(), b"existing user data")

  def test_existing_demo_still_renders(self):
    output = self.root/"legacy.png"
    result = render(ROOT/"examples/demo.json", output, font=self.font, still=8)
    self.assertEqual(result["type"], "still")
    self.assertTrue(output.is_file())


if __name__ == "__main__":
  unittest.main()
