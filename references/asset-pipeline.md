# 歌词对齐、角色精灵与分层场景

## 歌词时间轴

先准备 UTF-8 纯文本歌词，一行一句；歌词内容由用户确认。使用已安装的 [WhisperX](https://github.com/m-bain/whisperX) 生成带词时间的 JSON，或把已有 JSON 交给对齐脚本：

```sh
# 从已有 WhisperX JSON 创建可编辑草稿：
python3 scripts/align_lyrics.py --lyrics my-lyrics.txt --asr-json whisperx.json --out output/lyrics-draft.json

# 可选：已自行安装 WhisperX 时，用本地音频运行识别与对齐：
python3 scripts/align_lyrics.py --lyrics my-lyrics.txt --audio my-song.wav --language zh --out output/lyrics-draft.json

# 在编辑器听音修正后，再供渲染器使用：
python3 scripts/render_mv.py my-storyboard.json --audio my-song.wav --lyrics output/lyrics-draft.json --out output/mv.mp4
```

WhisperX 是**可选依赖**，不包含在本仓库的基础依赖中；它的模型、语言对齐模型和依赖可能需要联网下载，离线运行前需先准备好。默认 `cpu`、`int8`、`small`；可通过 `--device`、`--compute-type`、`--model` 调整。脚本不会自动上传音频；WhisperX 的安装和模型来源请按其官方文档确认。人声分离可作为额外的人工步骤，并非脚本内置功能。

输入 JSON 要有 `segments[].words[]`，每词包含 `word`、`start`、`end`，时间以视频开始为零点的秒为单位。脚本将确认文本与识别结果按顺序匹配，标点保留原样，同一个 ASR 词不会被虚构拆成多个独立时间。每句的 `match_coverage` 只是文字匹配比例，不是时间准确率。重复副歌、错识别、拖音、和声或同词跨行都可能使结果不可靠。

- `status: draft`：已匹配但**仍须听音检查**并修正时间、文本和 token；不代表已校验。
- `status: review_required`：缺字、无匹配或词跨行，不会生成臆测的时间；渲染器会拒绝，先人工补上非重叠的 `start/end/tokens`，并把 `status` 改为 `manual` 或 `draft`。如果只能确定句级时间，可将 `tokens` 设为空，使用近似阅读高亮并注明。
- `tokens` 文本必须完整拼接为对应句，时间依次不重叠且在句内；注意听音确认首尾与歌曲一致。对齐数据中的时间早于 0、重叠或缺失会明确报错。

导入歌词 JSON 时，有 token 的行默认使用卡拉 OK 模式；无 token 的行使用分镜的 `subtitle_mode`。同样支持原有 `.lrc`；其中的逐字动画仍是估算。输出 `.render.json` 只记录来源和时间粒度，不代表已听音核验。

## 角色精灵 PNG

在分镜 JSON 中按角色名配置 `sprites`；路径相对于该 JSON。PNG 为规则网格，从左到右、从上到下编号，左上角编号为 0。透明区域用 alpha 通道。`anchor` 是每帧相对于左上角的脚底点，各帧尺寸及锚点必须一致。

```json
{
  "sprites": {
    "hero": {
      "image": "assets/hero.png", "frame_width": 12, "frame_height": 19,
      "anchor": [6, 19],
      "portrait": "assets/hero-portrait.png",
      "animations": {
        "idle": {"front": {"frames": [0], "fps": 6}},
        "walk": {"front": {"frames": [0, 1, 2, 3], "fps": 6, "loop": true}}
      }
    }
  }
}
```

`portrait` 可省略，默认使用第一帧上部裁剪；`loop` 默认为 true，设为 false 时停在末帧。预设场景的 `hero`、`partner` 会使用对应自定义精灵；没配置的角色使用内置造型。请为每个实际使用的动作及朝向都配置动画（包括 `idle`、`walk`、`jump` 或 `play`）；缺失会报错，不会偷偷换成另一个动作。预设的 `play` 会额外绘制内置乐器，公交车厢中的群像也会复用 hero/partner。自定义人物的衣服、视角和像素比例应在整片保持一致。

## composite 场景与视差

可直接运行 `examples/composite-demo.json`。这是原创图层素材和原创文案的无声示例：

```sh
python3 scripts/render_mv.py examples/composite-demo.json --still 3 --out output/layer-frame.png
python3 scripts/render_mv.py examples/composite-demo.json --out output/layer-demo.mp4
```

顶层 `canvas` 支持 `[256,144]`（默认）或 `[320,180]`。320×180 目前仅支持 `composite` 场景；内置预设场景使用 256×144。输出尺寸是画布乘以整数 `scale`，采用最近邻放大。

```json
{
  "kind": "composite", "start": 0, "end": 8,
  "camera": {"world": "street", "speed": 12},
  "layers": [
    {"id": "sky", "type": "image", "file": "assets/sky.png", "z": 0, "parallax": 0},
    {"id": "city", "type": "image", "file": "assets/city.png", "z": 1,
     "repeat_x": true, "parallax": 0.3},
    {"id": "hero", "type": "sprite", "actor": "hero", "action": "walk", "view": "front",
     "z": 2, "x": 100, "y": 140, "scale": 2, "parallax": 0,
     "keyframes": [{"time": 0, "x": 100}, {"time": 8, "x": 160}]}
  ]
}
```

- `image` 图层用左上角定位；`sprite` 图层用其脚底 `anchor` 定位。按 `z` 从小到大绘制，相同 `z` 保留列表顺序。
- 图层 `x/y`、`keyframes` 的坐标是逻辑像素，`time/start/end` 均为视频绝对秒数。关键帧可设置 `x/y/opacity`，按时间线性插值，实际绘制坐标取整。`opacity` 范围 0–1；图层 `scale` 为 1–8 的整数。
- `camera.speed` 单位是逻辑像素/秒；每层减去相机位置乘以 `parallax`。`0` 固定在屏幕，`1` 随世界完整滚动；图像图层可 `repeat_x: true` 循环铺设。相同叙事分支及 `world` 的相机位置可跨场景继承。
- 多场景中只有引用相同 `world` 的镜头会连续滚动。快进事件目前仅支持 `candy_road`；composite 不自动提供雨丝、粒子或复杂镜头，需以图层和关键帧设计。
- 避免把歌词直接画进背景图；字幕由渲染器叠加。建议为角色头、脚、歌词和 HUD 预留空间，并人工检查遮挡。
