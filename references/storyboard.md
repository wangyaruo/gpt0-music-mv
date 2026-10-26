# 歌词到分镜：可执行契约

## 编排

把每句歌词标为物件、动作、关系、地点、情绪或收束，再给它一个游戏机制。
例如“带上勇气出发”可以成为装备确认、走出菜单和向右跑；
“把烦恼留在身后”可以成为音符击退怪物，角色继续前进；
不要因为参考片有海滩，就把雪夜或都市歌词强行搬去海边。

短句可以共享一个场景，长句可以拆成状态推进。通常以 2–8 秒的事件单元为起点，按真实歌词时长调整。
连续性状态建议包含：角色位置/朝向、装备、金币、生命、关系、关卡、一天中的时间。
让叙事重音落在音乐的重拍或分句，而不是机械按固定秒数切换。

## JSON 结构

直接复制 `examples/demo.json` 后改写。所有数值时间以秒计。

顶层字段：
- `title`、`credit`：片名和用户指定署名；不要继承参考视频的艺人名。
- `duration`：成片时长。
- `fps`：输出帧率，默认 30；角色动作独立采用约 8 fps。
- `scale`：256×144 逻辑画布的整数放大倍数，默认 4。
- `bpm`、`beat_offset`：已确认或人工修正的节拍参数；不是凭歌词猜出的 BPM。
- `audio`、`lyrics_file`、`font`：可选路径，相对于 JSON 文件；CLI 参数优先。
- `crt`：是否叠加轻微扫描线、暗角和固定显示器透视。
- `scenes`：从 0 连续覆盖 duration 的镜头数组，不允许空洞或重叠。
- `lyrics`：句级字幕数组，`start/end/text` 必填，可选 `reveal_seconds`；不能跨句重叠。

每个 scene：
- `start/end`：起止秒数；end 不包含。
- `kind`：title / beach / equipment / drive / battle / map / spotlight / night / ending。
- `palette`：day / sunset / night，决定光照世界。
- `label`：右上关卡名或菜单名。
- `action`：walk / jump / play / idle。
- `partner`：是否出现第二角色；`coins` 为进入该镜头时的累计值，后续不能无故减少。
- `meaning`：创作时写明对应的歌词意义和状态变化，不参与绘制。
- `background`：可选 PNG/JPEG，按最近邻缩放到逻辑画布；人物和 UI 仍由渲染器绘制。

人物是固定原创 sprite，示例替换人物请编辑 `scripts/pixel_world.py` 的 sprite 图案与色板；
要接入外部精灵图集时，根据明确的帧宽/帧高/透明通道写加载器，不凭一张不规则 AI 拼图猜切片。
现有 renderer 不宣称支持未实现的剧情镜头；为新 kind 增加对应绘制函数和验证，再写入配置。

## 字幕

支持标准 LRC `[mm:ss.xx]歌词`、同一行多时间戳和 `[offset:毫秒]`；忽略标题/艺人元数据标签。
LRC 每句结束于下一句开始，最后一句结束于片长；显式 JSON 时间轴优先用来精确控制停留。
CLI `--lyrics` 会覆盖 JSON 的 `lyrics`；外部音频用 `--audio` 覆盖。

播放器先对完整句子布局，再逐字揭示字符，所以字幕不会随着字数增加跳行。
两行容不下的句子会报错；改为更合理的句段，不能静默裁掉字幕。
普通 LRC 只有句级时间，逐字揭示只是阅读动画，不等于逐字演唱对齐。

## 资产提示词骨架（仅需要生成新资产时使用）

背景：`16-bit pixel art [地点], [时间/配色], side-scrolling RPG background,
clear walkable ground in the lower third, layered sky/distance/midground,
limited palette, hard pixel edges, no text, no UI, no characters`。

角色：`original chibi pixel RPG character, [固定发型/衣服/道具], front three-quarter view,
consistent 16x20-pixel proportions, crisp pixel clusters, transparent background, no text`。

先确认一个角色母版，再生成动作变体；固定像素密度、调色板、朝向和透明边缘。
字幕/HUD 留给确定性绘制，不能在每个生成镜头里重新画不同样式的 UI。
