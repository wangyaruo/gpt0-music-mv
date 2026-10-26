# gpt0-music-mv

一个可复用的 **像素 RPG 叙事音乐视频 skill**：把歌词变成装备、关卡、NPC 对话、音符战斗、世界地图和宝箱奖励，再用固定角色、游戏 HUD 与逐字对白把它们串成 MV。

基于用户提供的一支约 **2 分 55 秒、1024×576、30 fps** 的参考视频拆解。完整观察见 [参考视频分析](references/reference-analysis.md)。

![原创示例的九种场景](assets/preview.png)

上图来自本仓库实际渲染的 24 秒原创文案无声预览。它展示可运行的风格原型，未使用参考视频画面、原曲或原歌词。

## 用作 Codex skill

将本仓库目录放在你的 skills 目录下，目录名保持 `gpt0-music-mv`。例如：

```sh
git clone https://github.com/wangyaruo/gpt0-music-mv.git ~/.codex/skills/gpt0-music-mv
```

在支持 skills 的环境中调用：

> 使用 $gpt0-music-mv，把我提供的歌曲和 LRC 歌词做成像素 RPG 音乐视频。先把歌词转为游戏事件，再制作固定角色和连贯的关卡叙事。

入口是 [SKILL.md](SKILL.md)，详细分镜字段和资产提示词见 [分镜契约](references/storyboard.md)。
它不绑定某个付费图像/视频服务，也不宣称能凭成片判断原作者使用的模型。

## 直接运行

需要 Python 3.10+、Pillow、FFmpeg 和支持中文的字体。

```sh
python3 -m pip install -r requirements.txt

# 24 秒无声预览：生成 1024×576、30 fps、H.264 MP4。
python3 scripts/render_mv.py examples/demo.json --out output/demo.mp4

# 检查一个关键画面。
python3 scripts/render_mv.py examples/demo.json --still 6.5 --out output/equipment.png

# 分析你的参考视频：元数据、带时间戳抽帧、联系表、转场候选和音频信号指标。
python3 scripts/analyze_video.py /path/reference.mp4 --out output/analysis
```

FFmpeg 不在 PATH 时，加 `--ffmpeg /path/to/ffmpeg`，也可设置 `FFMPEG_BIN`。
找不到中文字体时，加 `--font /path/to/NotoSansCJK-Regular.ttc`，也可设置 `MV_FONT`。
脚本会寻找常见的 macOS、Linux 和 Windows 中文字体；字体本身不随仓库分发。

## 用你自己的歌曲

1. 复制 `examples/demo.json` 为自己的分镜。
2. 把 `duration` 和 `scenes` 改为真实歌曲时间线，镜头连续覆盖整首歌。
3. 为每句歌词设计一个有动作和结果的游戏事件，按需要替换角色或扩展场景。
4. 传入音频和句级歌词；人工核对同步后交付。

```sh
python3 scripts/render_mv.py my-storyboard.json \
  --audio my-song.wav --lyrics my-song.lrc --out output/my-mv.mp4
```

JSON 内的 `audio`、`lyrics_file`、`font`、场景 `background` 路径相对于 JSON 文件；CLI 参数路径相对于当前目录。
不提供音频会明确输出无声预览。音频短于成片会报错，不偷偷循环、变速或补静音。
输出已存在时默认报错；明确替换产物可加 `--overwrite`。

### 当前能力

| 能力 | 实现 |
|---|---|
| 像素场景 | 白昼、夕阳、夜景；海面、太阳/月亮、云、棕榈和星空 |
| 游戏叙事 | title / beach / equipment / drive / battle / map / spotlight / night / ending |
| 角色动画 | 原创角色、走路、跳跃、弹奏、头像、双人同场 |
| 状态与字幕 | 心形 HUD、非递减金币、关卡名、两行对白、逐字出现 |
| 歌词 | JSON 句级时间轴、标准 LRC、多时间戳、offset |
| 视频 | 最近邻整数放大、轻 CRT、H.264、可选 AAC 音频、成片元数据检查 |
| 参考分析 | 定时抽帧、联系表、转场候选；安装可选 NumPy 后提供 BPM 候选 |

原片中的酒吧、俯视脚印、篝火和更复杂的镜头运动并未冒充已实现功能；skill 会指导为新分镜扩展绘制函数或提供资产。
程序化像素资产在 `scripts/pixel_world.py` 中，可替换配色、人物图案和场景。
现有示例不含自动语音识别、逐字演唱对齐或自动音乐生成。BPM 候选存在半拍/倍拍歧义，必须核对。

## 仓库结构

```text
SKILL.md                      技能入口
agents/openai.yaml            技能展示信息
references/reference-analysis.md  原片观察、实测参数与结构
references/storyboard.md      歌词映射、分镜契约、资产提示词
scripts/analyze_video.py      参考视频分析
scripts/render_mv.py          时间轴、对白与视频合成
scripts/pixel_world.py        原创像素角色和场景
scripts/media_utils.py        FFmpeg 查找与元数据读取
examples/demo.json            可直接渲染的九场景样例
assets/preview.png            由样例生成的画面预览
tests/test_timeline.py        时间轴和 LRC 行为检查
```

## 验证

```sh
python3 -m unittest discover -s tests -v
```

开发验证已实际执行：
- 6 项时间轴/LRC 检查通过。
- 24 秒无声示例：1024×576、30 fps、H.264，时长与配置一致。
- 2 秒自制测试音频合成：确认 MP4 存在音轨且时长正确；测试音不是示例配乐。
- 分析脚本运行于原始视频：18 张抽帧、30 个合并后的画面变化候选。
- 查看九个关键场景的渲染预览，确认中文与对白区域可见。

`output/`、原始视频及音频文件都被 Git 忽略。此仓库只发布 skill、代码、原创示例配置和原创预览图。

实现参考：[FFmpeg 文档](https://ffmpeg.org/ffmpeg.html)、[Pillow Image 文档](https://pillow.readthedocs.io/en/stable/reference/Image.html)。
