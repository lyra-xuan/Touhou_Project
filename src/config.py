"""全局常量配置。

集中管理分辨率、帧率、颜色与各类实体参数，避免魔法数字散落在各处。
"""
from __future__ import annotations

# ---------- 窗口与帧率 ----------
SCREEN_W, SCREEN_H = 1280, 960
FPS = 60
# 单帧最大时间步长：卡顿/窗口拖动后 dt 会很大，夹紧可避免物体“瞬移”穿过判定区
MAX_DT = 1.0 / 30.0

# ---------- 颜色 ----------
BLACK = (8, 5, 11)
WHITE = (241, 226, 207)
RED = (204, 43, 58)
CYAN = (150, 196, 220)
YELLOW = (224, 184, 112)
GRAY = (91, 75, 76)
BLUE = (110, 150, 255)
GOLD = (187, 145, 83)
PALE_GOLD = (231, 201, 151)
PANEL = (14, 8, 15)
MUTED = (157, 133, 125)

# 弹幕配色：作为键去匹配素材贴图，与实际像素颜色无关
GREEN = (67, 255, 61)
MAGENTA = (255, 27, 254)
PURPLE = (118, 95, 255)

# ---------- 战斗区域 ----------
PLAYFIELD_LEFT = 32
PLAYFIELD_TOP = 32
PLAYFIELD_WIDTH = 768
PLAYFIELD_HEIGHT = 896
PLAYFIELD_RIGHT = PLAYFIELD_LEFT + PLAYFIELD_WIDTH
PLAYFIELD_BOTTOM = PLAYFIELD_TOP + PLAYFIELD_HEIGHT
PLAYER_START_X = PLAYFIELD_LEFT + PLAYFIELD_WIDTH / 2
PLAYER_START_Y = PLAYFIELD_BOTTOM - 120

# ---------- 玩家 ----------
PLAYER_SPEED = 560.0        # 像素/秒
PLAYER_FOCUS_FACTOR = 0.45  # 按住 Shift 低速移动时的速度系数
PLAYER_POWER_START = 1.00   # 默认初始火力（实际以 POWER_STAGE_CURVE 的关卡保底为准）
POWER_UP_BANNER_DURATION = 0.9  # 自机升档时「火力上昇」提示的显示时长（秒）
# 火力档位表：(进入该档所需的火力下界, 自机弹的横向偏移)。
# 依次为 单发 → 双发 → 三发 → 满火力四发；要加档位就往这里追加一行，
# 并在 art.PLAYER_SHOT_LEVELS 里补一张同序号的贴图。
POWER_TIERS = (
    (1.00, (0.0,)),
    (2.00, (-10.0, 10.0)),
    (3.00, (-14.0, 0.0, 14.0)),
    (4.00, (-18.0, -6.0, 6.0, 18.0)),
)
# 火力成长：战斗中每隔 POWER_TIME_STEP_SECONDS 秒自动 +POWER_GAIN_STEP，
# 但不会超过当前关卡的上限；拾取红玉额外 +POWER_GAIN_PICKUP，可突破上限。
POWER_TIME_STEP_SECONDS = 2.5
POWER_GAIN_STEP = 0.05
POWER_GAIN_PICKUP = 0.10
# 每关的火力曲线：(关卡开始时的保底火力, 该关自动成长的上限)
POWER_STAGE_CURVE = (
    (1.00, 2.00),   # 第 1 关：1.00 起步，最多自动升到双发
    (2.00, 3.00),   # 第 2 关：保底双发，最多自动升到三发
    (3.00, 4.00),   # 第 3 关：保底三发，自动升到满火力
)
PLAYER_HIT_RADIUS = 4.5     # 命中判定半径（弹幕游戏惯例：极小）
PLAYER_GRAZE_RADIUS = 27.0  # 擦弹判定半径（外层）
PLAYER_START_MARGIN = 120.0
PLAYER_SPRITE_WIDTH = 46   # 素材原始 23×43，按 2 倍显示
PLAYER_SPRITE_HEIGHT = 86
PLAYER_LIVES = 3
PLAYER_INVULNERABLE_TIME = 1.5
PLAYER_SHOT_SPEED = 720.0
PLAYER_SHOT_RADIUS = 6.0
PLAYER_SHOT_DAMAGE = 10.0
PLAYER_FIRE_INTERVAL = 0.18

# ---------- 子弹 ----------
BULLET_RADIUS = 7.5
BULLET_SMALL_RADIUS = 8.0
BULLET_LARGE_RADIUS = 13.0
BULLET_MID_RADIUS = 11.0

# ---------- Boss ----------
BOSS_START_X = PLAYER_START_X
BOSS_START_Y = PLAYFIELD_TOP + 148.0
BOSS_RADIUS = 42.0
BOSS_ATTACK_ORIGIN_OFFSET = (0.0, 38.0)  # 从立绘中心下移至身体，避免弹幕从脸部发射
# 血量与符卡数由 spells.BossSpec 决定，这里只保留运动与限时
BOSS_MOVE_SPEED = 240.0
BOSS_LEFT_BOUND = PLAYFIELD_LEFT + 128.0
BOSS_RIGHT_BOUND = PLAYFIELD_RIGHT - 128.0
BOSS_ATTACK_SPEED = 232.5
BOSS_PHASE_TIME_LIMIT = 45.0  # 符卡限时的缺省值（秒），实际以 SpellCard.duration 为准
BOSS_PHASE_DROP_POWER = 6     # 每次进入新阶段时掉落的火力道具数
SPELL_ANNOUNCE_DURATION = 2.8  # 符卡名与技能描述的播报时长（秒）

# ---------- 计分 ----------
GRAZE_SCORE = 500       # 每次擦弹
VICTORY_SCORE = 10000   # 击破关底 Boss
HISCORE_FILE = "hiscore.txt"
PROGRESS_FILE = "progress.json"

# ---------- 特效时长（秒） ----------
HIT_SPARK_DURATION = 0.20
GRAZE_RING_DURATION = 0.28
BURST_DURATION = 0.60
BOSS_FLASH_DURATION = 0.16

# ---------- 打击感 ----------
HIT_SPARK_END_SCALE = 1.35   # 命中火花的最终缩放（原先 1.1，放大更醒目）
HIT_SPARK_SHAKE = 3.0        # 玩家弹命中 Boss / 妖精时的微幅震屏幅度（像素）
PLAYER_HIT_SHAKE = 16.0      # 自机被命中时的震屏幅度（像素）
SCREEN_SHAKE_DECAY = 46.0    # 震屏幅度每秒衰减速度（像素/秒）

# ---------- 特殊技能（蓄力 → 释放 → 后摇） ----------
SKILL_CHARGE_TIME = 1.2      # Boss 特殊技能的默认蓄力时长（秒）
SKILL_RECOVER_TIME = 0.8     # 后摇时长（秒）
SKILL_SHAKE = 14.0           # 释放特殊技能时的震屏幅度（像素）
SKILL_SHOCKWAVE_DURATION = 0.55  # 释放瞬间扩散的冲击波光环时长（秒）

# 自机特技（C 键）：短蓄力发动「时间凝滞」，令全场敌弹整体减速。
# 不清弹、也不对 Boss 造成伤害，纯粹是争取走位窗口的保命 / 反攻手段。
PLAYER_SKILL_NAME = "夢符「二重結界」"
PLAYER_SKILL_CHARGE_TIME = 1.2     # 自机特技的短蓄力时长（秒）
PLAYER_SKILL_SLOW_FACTOR = 0.25    # 技能期间敌弹速度倍率（越慢越像时间凝滞）
PLAYER_SKILL_SLOW_DURATION = 5.0   # 敌弹减速的持续时长（秒）

# Boss 特殊技能：按剩余血量比例分档发动，且档位间距逐次收窄，
# 于是血量越低发动得越频繁。每个 Boss 都有自己的多段弹幕组合与主题色。
BOSS_SKILL_FIRST_HP = 0.80    # 首次触发的血量比例
BOSS_SKILL_HP_FACTOR = 0.7    # 每次触发后阈值按此比例下移（越小越低血量时越频繁）
BOSS_SKILL_FLASH = 0.40       # 释放瞬间的全屏闪光时长（秒）

# ---------- 弹幕场暗角 ----------
VIGNETTE_COLOR = (10, 3, 9)
VIGNETTE_MAX_ALPHA = 205

# ---------- 掉落道具 ----------
ITEM_RADIUS = 16.0          # 拾取判定半径
ITEM_FALL_SPEED = 120.0     # 匀速下落速度（像素/秒）
ITEM_MAGNET_RADIUS = 120.0  # 自机吸附范围
ITEM_MAGNET_SPEED = 560.0   # 吸附时的收拢速度
ITEM_COLLECT_LINE = PLAYFIELD_TOP + 112.0  # 到达此高度即自动回收全屏道具
ITEM_POWER_MAX = 4.00       # 火力上限（满火力四发）
ITEM_POINT_SCORE = 500      # 每枚 Point 道具的得分
ITEM_POWER_FULL_SCORE = 1000  # 满火力时拾取 Power 折算的分数
# 道具种类 -> 素材名；素材复用现有弹型贴图（红=火力，青=点数，绿=1UP）
ITEM_KINDS = ("power", "point", "life")
ITEM_KIND_COLORS = {
    "power": RED,
    "point": CYAN,
    "life": GREEN,
}

# ---------- 杂兵 ----------
FAIRY_HP = 16.0            # 击破所需的伤害
FAIRY_RADIUS = 22.0        # 命中判定半径
FAIRY_POINT_DROPS = 1      # 每只击破妖精掉落的道具数
FAIRY_DROP_PATTERN = ("point", "power", "point")
FAIRY_LIFE_DROP_CHANCE = 0.035

# ---------- 关卡流程 ----------
STAGE_COUNT = 3
STAGE_BANNER_DURATION = 2.6      # 关卡标题过场的停留时间（秒）
STAGE_CLEAR_BONUS = 20000        # 通过一关的结算奖励
MIDBOSS_SCORE = 8000             # 击破中 Boss 的得分
BOSS_SPELL_BASE_BONUS = 2000     # 破符基础奖励
BOSS_SPELL_TIME_BONUS = 600      # 破符时每剩余 1 秒追加的奖励
MIDBOSS_HP = 650.0               # 中 Boss 总生命值
STAGE_CLEAR_DELAY = 1.4          # Boss 击破后到下一关/结局的停留时间

# ---------- 玩家符卡 · 灵击（Bomb） ----------
PLAYER_BOMB_START = 3            # 初始符卡数
PLAYER_BOMB_MAX = 5              # 符卡上限
PLAYER_BOMB_RECHARGE = 4.0       # 每 4 秒自动回复 1 枚
PLAYER_BOMB_REUSE_GAP = 0.5      # 本次灵击结束后 0.5s 即可再次使用
PLAYER_BOMB_DURATION = 2.6       # 灵击持续（无敌 + 清弹）时间
PLAYER_BOMB_RADIUS = 360.0       # 灵击生效半径
PLAYER_BOMB_BULLET_SCORE = 100   # 被灵击消去的每颗子弹折算分数
PLAYER_BOMB_CLEAR_ITEM_CAP = 24  # 灵击最多化作的道具数，避免刷屏
PLAYER_BOMB_NAME = "霊符「夢想封印」"

# ---------- 波次编排 ----------
WAVE_ENTRY_MARGIN = 30.0         # 编队从弹幕场顶边外多远处进入
WAVE_LULL = 0.6                  # 两波之间的默认缓冲时间

# ---------- 空间网格 ----------
GRID_CELL_SIZE = 96

# ---------- 碰撞调试可视化 ----------
DEBUG_OVERLAY_DEFAULT = False   # 启动时是否直接显示调试层
DEBUG_GRID_COLOR = (62, 78, 96)
DEBUG_GRID_ALPHA = 80
DEBUG_HIT_COLOR = (255, 92, 92)      # 命中区（内层，致命）
DEBUG_GRAZE_COLOR = (120, 196, 255)  # 擦弹区（外层，不致命）
DEBUG_SWEEP_COLOR = (255, 198, 104)  # 本帧扫掠线段

# ---------- 存档调试 ----------
DEBUG_PERSISTENCE = False   # 打开后会在存档写入失败时打印原因
