import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
from analyze_song import analyze
from media_utils import ffmpeg_path
from rain_scenes import render_rain_scene


class SceneWeatherTests(unittest.TestCase):
  def test_bus_stop_default_is_clear_but_rain_can_be_requested(self):
    scene = {'kind': 'bus_stop', 'start': 0, 'end': 2}
    with patch('rain_scenes.rain') as draw_rain:
      render_rain_scene(scene, 1)
      self.assertEqual(draw_rain.call_count, 0)
      render_rain_scene(dict(scene, weather='rain'), 1)
      self.assertEqual(draw_rain.call_count, 2)

  def test_rain_city_still_rains_and_example_uses_explicit_weather(self):
    with patch('rain_scenes.rain') as draw_rain:
      render_rain_scene({'kind': 'rain_city', 'start': 0, 'end': 2}, 1)
      self.assertEqual(draw_rain.call_count, 2)
    demo = json.loads((ROOT/'examples/rain-demo.json').read_text(encoding='utf-8'))
    self.assertTrue(all(scene.get('weather') == 'rain' for scene in demo['scenes'] if scene['kind'] == 'bus_stop'))


class SongAnalysisTests(unittest.TestCase):
  def test_local_signal_measurements_do_not_claim_a_mood(self):
    try:
      executable = ffmpeg_path()
    except ValueError as error:
      self.skipTest(str(error))
    with tempfile.TemporaryDirectory() as temp:
      root = Path(temp)
      audio = root/'tone.wav'
      with wave.open(str(audio), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(struct.pack('<h', 1000)*16000 + struct.pack('<h', 0)*16000)
      report = analyze(audio, root/'analysis.json', interval=1, ffmpeg=executable)
      self.assertEqual(len(report['segments']), 2)
      self.assertAlmostEqual(report['duration'], 2)
      self.assertGreater(report['segments'][0]['rms_dbfs'], report['segments'][1]['rms_dbfs'])
      self.assertIn('不能自动判断情绪', report['interpretation'])
      with self.assertRaises(ValueError):
        analyze(audio, root/'analysis.json', ffmpeg=executable)
      with self.assertRaises(ValueError):
        analyze(audio, audio, ffmpeg=executable, overwrite=True)


if __name__ == '__main__':
  unittest.main()
