# 歌词到分镜：可执行契约

## 编排

把每句歌词标为物件、动作、关系、地点、情绪或收束，再给它一个游戏机制。
例如“带上勇气出发”可以成为装备确认、走出菜单和向右跑；
“把烦恼留在身后”可以成为音符击退怪物，角色继续前进；
不要因为参考片有海滩，就把雪夜或都市歌词强行搬去海边。

短句可以共享一个场景，长句可以拆成状态推进。通常以 2–8 秒的事件单元为起点，按真实歌词时长调整。
连续性状态建议包含：角色位置/朝向、装备、金币、生命、关系、队伍、距离、记忆物品、关卡和故事时间。
播放时间始终递增；故事时间可以切到回忆或假设分支。状态变化应由可观察事件解释。
让叙事重音落在音乐的重拍或分句，而不是机械按固定秒数切换。

## JSON 结构

直接复制 `examples/demo.json` 后改写。所有数值时间以秒计。

顶层字段：
- `title`、`credit`：片名和用户指定署名；不要继承参考视频的艺人名。
- `duration`：成片时长。
- `fps`：输出帧率，默认 30；角色动作独立采用约 8 fps。
- `animation_fps`：角色有限帧动作频率，默认 8，可设 1–30；与 `fps` 分开控制。
- `scale`：256×144 逻辑画布的整数放大倍数，默认 4。
- `bpm`、`beat_offset`：已确认或人工修正的节拍参数；不是凭歌词猜出的 BPM。
- `audio`、`lyrics_file`、`font`：可选路径，相对于 JSON 文件；CLI 参数优先。
- `crt`：是否叠加轻微扫描线、暗角和固定显示器透视。
- `scenes`：从 0 连续覆盖 duration 的镜头数组，不允许空洞或重叠。
- `lyrics`：句级字幕数组，`start/end/text` 必填，可选 `reveal_seconds`；不能跨句重叠。
- `subtitle_mode`：`dialogue`（默认的对白框逐字显示）或 `karaoke`（底部白/粉/灰逐字高亮）。单句可用 `mode` 覆盖。

每个 scene：
- `start/end`：起止秒数；end 不包含。
- `kind`：title / beach / equipment / drive / battle / map / spotlight / night / ending / rain_city / bus_stop / bus_interior / classroom / bookstore / memory_items / city_map。
- `palette`：day / sunset / night，决定光照世界。
- `label`：右上关卡名或菜单名。
- `action`：walk / jump / play / idle。
- `partner`：是否在画面中出现第二角色。未指定时可根据当前分支的 `state.party` 推断；显式值优先，因此角色离开队伍后仍可作为 NPC 留在画面中。
- `coins`：当前故事分支的金币数，默认继承前一场景；可以减少，但必须用 `event` 说明原因。
- `narrative_time`：present（默认）/ memory / alternate；`branch` 是分支名，默认 `main`。每个组合独立保存状态与金币，返回现实后恢复现实分支。
- `state`：当前分支的增量状态，可含 `party`（hero/partner 列表）、`affinity`（0–100）、`distance`（`{"value": 14, "unit": "km"}`，单位 km/m/cm）和 `inventory`（字符串列表）。已有字段发生变化时填写非空 `event`；未提及的字段沿用本分支上次的值。
- `event`：对状态变化或金币减少的简短原因说明。状态初次设置不要求 event，但写明会更容易检查剧情。
- `weather`：clear 或 rain。雨层当前用于 rain_city/bus_stop；其他场景默认清晰天气。
- `bus`：bus_stop 的 none / approach / leave。
- `umbrella`：`{"owner":"hero|partner|shared","color":"blue|pink"}`；适用于 rain_city、bus_stop、classroom、bookstore，partner/shared 要求同伴在场。雨伞由场景显式设置，不会自动跨场景继承。
- `hero_view`、`partner_view`：front / back / left / right，默认 front；示例精灵提供简化视角，不是完整的逐方向角色图集。
- `era_label`：回忆/假设分支的画面标记；回忆默认使用暖褐色，可用 `memory_filter: false` 关闭。
- `dialogue`：`{"speaker":"hero|partner","name":"同伴","text":"台词"}`，显示顶部头像对白。
- `choice`：`{"prompt":"继续吗？","options":["继续","离开"],"selected":0}`，显示预先编排的选择菜单；它是视频画面，不是交互式游戏。同一场景不能同时设置 dialogue 和 choice。
- `meaning`：创作时写明对应的歌词意义和状态变化，不参与绘制。
- `background`：可选 PNG/JPEG，按最近邻缩放到逻辑画布；人物和 UI 仍由渲染器绘制。

人物是固定原创 sprite，示例替换人物请编辑 `scripts/pixel_world.py` 的 sprite 图案与色板；
要接入外部精灵图集时，根据明确的帧宽/帧高/透明通道写加载器，不凭一张不规则 AI 拼图猜切片。
现有 renderer 不宣称支持未实现的剧情镜头；为新 kind 增加对应绘制函数和验证，再写入配置。

## 字幕

支持标准 LRC `[mm:ss.xx]歌词`、同一行多时间戳和 `[offset:毫秒]`；忽略标题/艺人元数据标签。
LRC 每句结束于下一句开始，最后一句结束于片长；显式 JSON 时间轴可精确控制停留。
CLI `--lyrics` 或 JSON `lyrics_file` 会覆盖内嵌的 `lyrics`；外部音频用 `--audio` 覆盖。

播放器先对完整句子布局，再逐字揭示字符，所以字幕不会随着字数增加跳行。
两行容不下的句子会报错；改为更合理的句段，不能静默裁掉字幕。
卡拉 OK 模式中，已推进文字为白、当前字/词为粉、尚未推进文字为灰。
每句可提供 `tokens`：例如 `{"text":"雨点","start":0,"end":0.8}`；所有 token 按时间排序、不重叠、位于该句内，拼接文本必须与完整句子一致。时间为视频绝对秒数。
`timing_source` 可标为 `manual`、`aligned` 或 `estimated`，默认 estimated；渲染元数据会统计这些来源，但不会核验用户声明。
没有 tokens 时，在句内按字符均匀推进并标记近似。普通 LRC 只有句级时间；均匀高亮不等于逐字演唱对齐。
有 token 时间戳也应听音核对。当前脚本不包含自动语音识别或强制对齐。

可运行示例见 `examples/rain-demo.json`：现实中的队伍状态、独立校园回忆、距离减少、假设选择和雨伞共用，以及一行带手工演示 token 的高亮。
示例歌词和时间戳均为演示数据，并非参考视频的歌词或音频转写。

## 资产提示词骨架（仅需要生成新资产时使用）

背景：`16-bit pixel art [地点], [时间/配色], side-scrolling RPG background,
clear walkable ground in the lower third, layered sky/distance/midground,
limited palette, hard pixel edges, no text, no UI, no characters`。

角色：`original chibi pixel RPG character, [固定发型/衣服/道具], front three-quarter view,
consistent 16x20-pixel proportions, crisp pixel clusters, transparent background, no text`。

先确认一个角色母版，再生成动作变体；固定像素密度、调色板、朝向和透明边缘。
字幕/HUD 留给确定性绘制，不能在每个生成镜头里重新画不同样式的 UI。
