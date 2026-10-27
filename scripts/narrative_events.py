"""Validate and evaluate deterministic visual events and scrolling between scenes."""
import copy
import math

KINDS = {"pickup", "gauge", "checkpoint", "stage_clear", "fast_forward", "cutin"}


def finite(value):
  return type(value) in (int, float) and math.isfinite(value)


def prepare_events(scene, initial_state, initial_coins):
  """Validate events and calculate the state at scene end without changing its initial snapshot."""
  events = scene.get("events", [])
  if not isinstance(events, list):
    raise ValueError("events 必须是列表。")
  for event in events:
    if (not isinstance(event, dict) or event.get("kind") not in KINDS or
        not all(finite(event.get(key)) for key in ("start", "end")) or
        not scene["start"] <= event["start"] < event["end"] <= scene["end"]):
      raise ValueError("事件需要有效的 kind，start/end 必须在当前场景内。")
  ordered = sorted(events, key=lambda item: (item["start"], item["end"]))
  gauge_values = copy.deepcopy(initial_state.get("gauges", {}))
  gauge_ends = {}
  visual_end = -1
  fast_end = -1
  for event in ordered:
    kind = event["kind"]
    if kind in ("checkpoint", "stage_clear", "cutin"):
      if event["start"] < visual_end:
        raise ValueError("checkpoint、stage_clear 和 cutin 的画面不能重叠。")
      visual_end = event["end"]
    if kind == "pickup":
      if (not isinstance(event.get("item"), str) or not event["item"].strip() or
          type(event.get("coins", 1)) is not int or not 0 <= event.get("coins", 1) <= 999):
        raise ValueError("pickup 需要非空 item 和 0–999 的整数 coins。")
    elif kind == "gauge":
      name, target = event.get("name"), event.get("to")
      if (not isinstance(name, str) or not 1 <= len(name) <= 8 or not finite(target) or not 0 <= target <= 100):
        raise ValueError("gauge 需要不超过 8 字的 name 和 0–100 的 to。")
      if event["start"] < gauge_ends.get(name, -1):
        raise ValueError("同一进度条的 gauge 事件不能重叠。")
      previous = gauge_values.get(name, 0)
      specified = event.get("from", previous)
      if not finite(specified) or not 0 <= specified <= 100:
        raise ValueError("gauge 的 from 必须在 0–100 之间。")
      if name in gauge_values and specified != previous:
        raise ValueError("gauge 的 from 必须与当前分支状态一致。")
      event["_from"] = specified
      gauge_values[name] = target
      if len(gauge_values) > 2:
        raise ValueError("一个分支最多支持两个进度条。")
      gauge_ends[name] = event["end"]
    elif kind == "fast_forward":
      factor = event.get("factor", 2)
      if scene["kind"] != "candy_road" or not finite(factor) or not 1 <= factor <= 16:
        raise ValueError("fast_forward 仅支持 candy_road，factor 必须在 1–16 之间。")
      if event["start"] < fast_end:
        raise ValueError("fast_forward 事件不能互相重叠。")
      fast_end = event["end"]
    elif kind == "cutin":
      if scene["kind"] != "candy_road" or event.get("style", "eyes") != "eyes" or event.get("actor", "hero") not in ("hero", "partner"):
        raise ValueError("cutin 仅支持 candy_road 的 eyes 及 hero/partner。")
    elif kind in ("checkpoint", "stage_clear"):
      if not isinstance(event.get("text", ""), str):
        raise ValueError("事件 text 必须是字符串。")
  final_state = copy.deepcopy(initial_state)
  final_coins = initial_coins
  for event in sorted(ordered, key=lambda item: (item["end"], item["start"])):
    if event["kind"] == "pickup":
      final_state.setdefault("inventory", []).append(event["item"])
      final_coins += event.get("coins", 1)
    elif event["kind"] == "gauge":
      final_state.setdefault("gauges", {})[event["name"]] = event["to"]
  return final_state, final_coins


def state_at(scene, time):
  """Calculate a frame's state, independent of the order in which frames are rendered."""
  state = copy.deepcopy(scene.get("_state", {}))
  coins = scene.get("coins", 0)
  events = sorted(scene.get("events", []), key=lambda item: (item["end"], item["start"]))
  for event in events:
    if event["kind"] == "pickup" and time >= event["end"]:
      state.setdefault("inventory", []).append(event["item"])
      coins += event.get("coins", 1)
    elif event["kind"] == "gauge" and time >= event["start"]:
      progress = min(1.0, (time-event["start"])/(event["end"]-event["start"]))
      value = event["_from"]+(event["to"]-event["_from"])*progress
      state.setdefault("gauges", {})[event["name"]] = value
  return state, coins


def scroll_position(scene, time):
  """Integrate the configured speed, with visual fast-forward only while its event is active."""
  end = max(scene["start"], min(time, scene["end"]))
  elapsed = end-scene["start"]
  for event in scene.get("events", []):
    if event["kind"] == "fast_forward":
      elapsed += max(0, min(end, event["end"])-event["start"])*(event.get("factor", 2)-1)
  return scene["_scroll_start"] + scene["_scroll_speed"]*elapsed
