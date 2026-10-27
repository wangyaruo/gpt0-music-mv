#!/usr/bin/env python3
"""Create a reviewable lyric timeline from corrected text and WhisperX JSON."""
import argparse
import difflib
import json
import math
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path


def normalized(text):
  return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def align(lines, data):
  words = []
  for segment in data.get('segments', []):
    for word in segment.get('words', []):
      text = word.get('word', '')
      start, end = word.get('start'), word.get('end')
      if not normalized(text):
        continue
      if (type(start) not in (int, float) or type(end) not in (int, float) or
          not math.isfinite(start) or not math.isfinite(end) or start < 0 or start >= end or
          (words and start < words[-1]['end'])):
        raise ValueError('识别结果存在缺失、重叠或无效的词时间；请先修正 ASR JSON。')
      words.append({'text': text, 'start': start, 'end': end})
  if not words:
    raise ValueError('识别结果没有带 start/end 的词；需要 WhisperX 对齐后的 words。')
  expected, locations = '', []
  for line_index, line in enumerate(lines):
    for char_index, char in enumerate(line):
      part = normalized(char)
      expected += part
      locations.extend([(line_index, char_index)] * len(part))
  recognized, owners = '', []
  for word_index, word in enumerate(words):
    part = normalized(word['text'])
    recognized += part
    owners.extend([word_index] * len(part))
  matches = {}
  matcher = difflib.SequenceMatcher(None, expected, recognized, autojunk=False)
  for block in matcher.get_matching_blocks():
    for offset in range(block.size):
      matches[block.a + offset] = owners[block.b + offset]
  per_line = [[] for _ in lines]
  for index, loc in enumerate(locations):
    per_line[loc[0]].append((loc[1], matches.get(index)))
  word_lines = {}
  for index, entries in enumerate(per_line):
    for _, owner in entries:
      if owner is not None:
        word_lines.setdefault(owner, set()).add(index)
  output = []
  for index, line in enumerate(lines):
    entries = per_line[index]
    matched = sum(owner is not None for _, owner in entries)
    coverage = matched / len(entries) if entries else 0
    owners_for_line = [owner for _, owner in entries if owner is not None]
    valid = (entries and matched == len(entries) and
             all(len(word_lines[owner]) == 1 for owner in owners_for_line) and
             owners_for_line == sorted(owners_for_line))
    row = {'text': line, 'start': None, 'end': None, 'tokens': [], 'timing_source': 'aligned',
           'status': 'review_required', 'match_coverage': round(coverage, 4)}
    if valid:
      char_owners = {}
      for pos, owner in entries:
        if pos in char_owners and char_owners[pos] != owner:
          valid = False
          break
        char_owners[pos] = owner
      if valid:
        groups = []
        for pos, char in enumerate(line):
          owner = char_owners.get(pos)
          if owner is None:
            if groups:
              groups[-1][1] += char
            else:
              groups.append([None, char])
          elif groups and groups[-1][0] == owner:
            groups[-1][1] += char
          elif groups and groups[-1][0] is None:
            groups[-1][0] = owner
            groups[-1][1] += char
          else:
            groups.append([owner, char])
        tokens = [{'text': text, 'start': words[owner]['start'], 'end': words[owner]['end']}
                  for owner, text in groups]
        row.update(start=tokens[0]['start'], end=tokens[-1]['end'], tokens=tokens, status='draft')
    output.append(row)
  return {'lyrics': output, 'metadata': {'source': 'whisperx-word-alignment',
          'review': '机器对齐草稿；必须听音校对，尤其是重复歌词和歌唱拖音。',
          'unresolved_lines': sum(row['status'] == 'review_required' for row in output)}}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--lyrics', required=True, help='人工确认的纯文本歌词，每行一句')
  source = parser.add_mutually_exclusive_group(required=True)
  source.add_argument('--asr-json', help='已有 WhisperX 对齐 JSON')
  source.add_argument('--audio', help='调用已安装的 whisperx；模型可能需要下载')
  parser.add_argument('--language', default='zh')
  parser.add_argument('--model', default='small')
  parser.add_argument('--device', default='cpu')
  parser.add_argument('--compute-type', default='int8')
  parser.add_argument('--out', required=True)
  parser.add_argument('--overwrite', action='store_true')
  args = parser.parse_args()
  try:
    output = Path(args.out)
    if output.exists() and not args.overwrite:
      raise ValueError('输出已存在；需要替换时加 --overwrite。')
    lines = [line.strip() for line in Path(args.lyrics).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not lines:
      raise ValueError('歌词文件为空。')
    if args.asr_json:
      data = json.loads(Path(args.asr_json).read_text(encoding='utf-8-sig'))
    else:
      executable = shutil.which('whisperx')
      if not executable:
        raise ValueError('未找到 whisperx；请先单独安装，或提供已有 --asr-json。')
      audio = Path(args.audio).resolve(strict=True)
      with tempfile.TemporaryDirectory(prefix='mv-align-') as temp:
        command = [executable, str(audio), '--language', args.language, '--model', args.model,
                   '--device', args.device, '--compute_type', args.compute_type,
                   '--output_format', 'json', '--output_dir', temp]
        subprocess.run(command, check=True)
        data = json.loads((Path(temp)/(audio.stem + '.json')).read_text(encoding='utf-8'))
    result = align(lines, data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('已写入 {}；{} 行无法自动对齐。所有行均需听音校对。'.format(output, result['metadata']['unresolved_lines']))
  except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
    parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
  main()
