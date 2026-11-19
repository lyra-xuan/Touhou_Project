# 美术与音效素材需求

## 已选方向

用户已选择**东方幻想乡原作风格方向**。标题页与战斗画面均直接复用用户提供并确认许可的图片素材；碰撞区域仍由代码单独定义，不依赖图片透明区域。

## 原作素材与音乐

“非商业”本身不等于可以直接提取和使用原作游戏资源。东方Project使用规定案的公开整理文本注明，二次创作中禁止直接使用原作游戏的图像素材、音乐、文本和程序。本仓库的 MIT License 仅适用于代码，不覆盖游戏素材；素材仍归各自权利人所有。本项目用户已确认标题页、战斗画面与音乐素材的许可均覆盖本项目使用；当前实际纳入的图片和来源记录在 `assets/title/ATTRIBUTION.md`、`assets/ATTRIBUTION.md`，音效见 `assets/audio/ATTRIBUTION.md`，背景音乐见 `assets/bgm/ATTRIBUTION.md`。

规则参考：[东方Project使用规定案（含原作素材使用条款）](https://thbwiki.cc/东方Project使用规定案)。这不是法律意见；使用素材时按已确认的许可范围执行并保留来源信息。

当前素材策略：标题页使用东方红魔乡标题图与音楽室背景 `music.jpg`，菜单文字由代码按原作「大字 + 红色光标」风格绘制，不再引用第三方菜单字图；战斗画面使用东方红魔乡的背景、自机、Boss 立绘、弹幕、特效与音效素材；背景音乐取自 TH06 原作 MIDI，并以 PC-98 时期原曲转码的 OGG 作为降级。新增素材须在 `assets/` 下登记来源、作者和许可范围。

## 当前已接入

战斗图像按类型保存在 `assets/character/`、`assets/bullet/`、`assets/effect/` 与 `assets/scene/`：包括三张关卡背景（人里近郊 / 雾之湖 / 红魔馆）、自机三组动画帧、中 Boss 与关底 Boss 立绘表情图集（自机与 6 名角色共 7 组）、大/中/小三种弹幕、玩家米弹、命中火花/擦弹光环/击破爆散特效，以及两组可击破杂兵动画。胜利流程使用红魔乡原作 `ED_DAT/end01.jpg` 作为后记背景、`ED_DAT/staff00.jpg` 作为鸣谢背景，并保留 `TL_DAT/result.jpg` 战绩插图；鸣谢页另从 `ED_DAT` 引入 6 张原作结局插画（`end02/end05/end06/end08/end10/end12.jpg` → `ending-roll-1~6.jpg`），在制作名单自下而上滚动时轮播淡入。「紅霧人物録」的「背景図鑑」页籤把这些整屏画面（三张关卡背景、四张结局图、战绩、标题、音楽室与六张结局插画，共 16 项）等比裁切后逐张翻阅。图集配套灰度遮罩在运行时按帧恢复透明边缘，来源与许可记录见 `assets/ATTRIBUTION.md`。掉落道具复用弹型贴图并添加 PWR / PTS / 1UP 标记区分。

音效副本保存在 `assets/audio/`：发射、命中、擦弹、警报、自机死亡、击破、阶段切换与三个菜单音，来源与许可记录见 `assets/audio/ATTRIBUTION.md`。音频加载或音频设备不可用时静默降级，不影响游戏运行。

背景音乐副本保存在 `assets/bgm/`：按场景重命名的 TH06 原作 MIDI（`title.mid`、`stage1~3.mid`、`boss-*.mid`、`ceremony.mid`、`ending.mid`、`credits.mid` 等）为主用音轨，PC-98 OGG（`title.ogg`、`stage.ogg`、`boss.ogg`、`ending.ogg`）作为解码失败时的降级。另保留原作编号副本 `th06_01.mid` ~ `th06_17.mid`，供「紅霧人物録 → 音楽室」页籤逐首试听，曲名与 ZUN 评论取自 `MD_DAT/musiccmt.txt`。来源与许可记录见 `assets/bgm/ATTRIBUTION.md`。音乐文件缺失或解码失败时静默降级，仅少一段声音。

战斗画布为 1280×960：左侧 768×896 弹幕场、右侧 Boss 与状态栏，参考 `project-striker` 的布局比例。弹幕场由关卡背景、暗红薄罩与径向暗角三层叠加，保证弹幕清晰；实体碰撞仍使用独立的几何半径。

## 最小素材清单

| 素材 | 建议规格 | 优先级 | 备注 |
|---|---:|---|---|
| 玩家机体 | 64×64 PNG，透明背景；可选 2-4 帧 | 必需 | 正面/俯视轮廓清楚，中心区域留出命中点 |
| Boss | 192×192 PNG，透明背景；可选 2-4 帧 | 必需 | 与玩家颜色、轮廓明显区分 |
| 圆形弹幕 | 16×16 或 24×24 PNG | 必需 | 至少两种颜色，用于区分弹幕模式 |
| 针形/椭圆弹幕 | 24×12 或 16×24 PNG | 可选 | 仅在第二种弹幕模式确实需要时制作 |
| 背景 | 1280×960 PNG，或可平铺图 | 必需 | 主体低对比，不能干扰弹幕辨识 |
| 命中/擦弹特效 | 64×64 PNG，2-4 帧 | 可选 | 已接入 `eff00` 的火花、光环与爆散 |
| 标题/胜负界面装饰 | 1280×960 PNG 或透明装饰层 | 可选 | 标题页、音楽室与胜负结算均已使用授权图片素材，菜单文字由代码绘制 |
| 音效 | OGG/WAV，短音效 | 可选 | 已接入 10 个：发射、命中、擦弹、警报、死亡、击破、阶段切换、菜单三音 |
| 背景音乐 | MIDI/OGG，循环段 | 可选 | 已接入 TH06 原作 MIDI 12 首 + PC-98 OGG 降级 4 首，另附全 17 曲供音楽室试听 |

## 暂定素材目录

```text
assets/
  title/
    ATTRIBUTION.md
    music-room.jpg
    touhou-th06-title.jpg
  character/
  bullet/
  effect/
  scene/
  ATTRIBUTION.md
  audio/
  bgm/
    ATTRIBUTION.md
    title.ogg
    stage.ogg
    boss.ogg
    ending.ogg
```

## 提供素材时请附带

- 文件名和预期用途。
- 是否可裁切、变色、加特效。
- 原作者/来源链接和许可；自行绘制可注明“原创”。
- 若是参考图，标注只参考配色、构图还是整体风格。

## 当前策略

玩家、Boss、弹幕、特效、妖精与音效均已使用 `assets/character/`、`assets/bullet/`、`assets/effect/`、`assets/scene/` 和 `assets/audio/` 中的授权素材，背景音乐使用 `assets/bgm/` 中的授权原曲转码；程序绘制仅保留为贴图缺失时的回退。素材来源分别记录在 `assets/title/ATTRIBUTION.md`、`assets/ATTRIBUTION.md`、`assets/audio/ATTRIBUTION.md` 和 `assets/bgm/ATTRIBUTION.md`。
