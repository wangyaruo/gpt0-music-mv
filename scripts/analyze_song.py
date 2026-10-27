#!/usr/bin/env python3
"""Measure song duration, approximate tempo and segment loudness locally."""
import argparse
import array
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from analyze_video import audio_stats
from media_utils import ffmpeg_path, probe


def segment_levels(path, seconds):
  levels = []
  with wave.open(str(path)) as reader:
    rate = reader.getframerate()
    block = max(1, round(seconds * rate))
    start = 0
    while True:
      samples = array.array('h', reader.readframes(block))
      if not samples:
        break
      if sys.byteorder != 'little':
        samples.byteswap()
      rms = math.sqrt(sum((value / 32768) ** 2 for value in samples) / len(samples))
      levels.append({'start': round(start / rate, 3), 'end': round((start + len(samples)) / rate, 3),
                     'rms_dbfs': round(20 * math.log10(max(rms, 1e-12)), 2)})
      start += len(samples)
  return levels


def analyze(audio, out, interval=15, ffmpeg=None, overwrite=False):
  source, output = Path(audio).resolve(strict=True), Path(out).resolve()
  if source == output:
    raise ValueError('分析输出不能覆盖输入音频。')
  if output.exists() and not overwrite:
    raise ValueError('输出已存在；确认替换时加 --overwrite。')
  if not math.isfinite(interval) or interval <= 0:
    raise ValueError('interval 必须为有限正数。')
  executable = ffmpeg_path(ffmpeg)
  metadata = probe(source, executable)
  if not metadata['has_audio']:
    raise ValueError('输入文件没有可用音轨。')
  with tempfile.TemporaryDirectory(prefix='song-analysis-') as tmp:
    decoded = Path(tmp) / 'audio.wav'
    command = [executable, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), '-vn',
               '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(decoded)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
      raise ValueError('音频解码失败：' + result.stderr[-3000:])
    stats = audio_stats(decoded)
    levels = segment_levels(decoded, interval)
  report = {'source': str(source), 'duration': stats['duration'], 'audio_signal': stats,
            'segments': levels,
            'interpretation': '音量和 BPM 候选只是信号测量，不能自动判断情绪、曲风、歌词、天气或场景。',
            'next_step': '结合完整歌词、用户意图和实际听感制作歌曲定位；节拍候选需听音核对。'}
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('audio')
  parser.add_argument('--out', required=True)
  parser.add_argument('--interval', type=float, default=15, help='分段音量测量窗口（秒）')
  parser.add_argument('--ffmpeg')
  parser.add_argument('--overwrite', action='store_true')
  args = parser.parse_args()
  try:
    result = analyze(args.audio, args.out, args.interval, args.ffmpeg, args.overwrite)
    print(json.dumps({'output': str(Path(args.out).resolve()), 'duration': result['duration'],
                      'tempo_status': result['audio_signal'].get('tempo_status')}, ensure_ascii=False, indent=2))
  except (ValueError, OSError) as error:
    parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
  main()
