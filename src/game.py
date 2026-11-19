"""游戏主循环与场景逻辑。

采用「夹紧的时间步长」推进逻辑：每帧用 ``clock.tick`` 得到真实 elapsed，
并夹紧到 ``MAX_DT``，保证物理与碰撞在不同机器上表现一致，同时避免卡顿后穿模。

关卡流程交给 :class:`~src.director.StageDirector`：它按剧本依次给出过场、对话、
杂兵波次与 Boss 战，本类只负责把返回的杂兵投放进场、按需生成 Boss、在 Boss
被击破时回报，并把当前状态画出来。
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import pygame
from pygame.math import Vector2

from . import config, collision, spells, hud, battle, render
from .art import GameArt
from .audio import Audio
from .director import BANNER, FIGHT, TALK, StageDirector
from .entities import Boss, BossBeam, Bullet, Effect, Fairy, Item, Player, PlayerShot

_wrap_text_to_width = hud.wrap_text_to_width


def _load_font(size: int) -> pygame.font.Font:
    """按优先级挑选一个能显示中文的系统字体。

    优先尝试 Windows 已知字体文件路径（避免 ``match_font`` 在 PyInstaller
    打包后扫描注册表崩溃），失败时再回退到 ``match_font``。
    """
    import os
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    for name in ("microsoftyahei", "simsun", "nsimsun", "simhei"):
        try:
            path = pygame.font.match_font(name)
        except Exception:
            path = None
        if path:
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    return pygame.font.Font(None, size)




def _build_vignette(size: tuple[int, int]) -> pygame.Surface:
    """生成径向暗角：中心透明、边缘压暗，把视线收拢到弹幕场中央。

    从最大半径往中心逐层绘制更小、更透明的圆，后画的盖住先画的。
    """
    width, height = size
    overlay = pygame.Surface(size, pygame.SRCALPHA)
    center = (width // 2, height // 2)
    max_radius = math.hypot(width, height) / 2
    steps = 64
    for step in range(steps):
        ratio = step / steps
        radius = max_radius * (1.0 - ratio)
        alpha = int(config.VIGNETTE_MAX_ALPHA * (1.0 - ratio) ** 2)
        pygame.draw.circle(
            overlay, (*config.VIGNETTE_COLOR, alpha), center, int(radius)
        )
    return overlay


def _cover_scale(surface: pygame.Surface,
                 size: tuple[int, int]) -> pygame.Surface:
    """等比缩放后居中裁切，让画面铺满目标尺寸（背景図鑑的预览框用）。"""
    target_w, target_h = size
    src_w, src_h = surface.get_size()
    scale = max(target_w / src_w, target_h / src_h)
    scaled = pygame.transform.smoothscale(
        surface, (max(1, round(src_w * scale)), max(1, round(src_h * scale)))
    )
    rect = pygame.Rect(0, 0, target_w, target_h)
    rect.center = scaled.get_rect().center
    return scaled.subsurface(rect).copy()


def _flash_sprite(sprite: pygame.Surface, amount: float) -> pygame.Surface:
    """把贴图整体加亮，用于 Boss 受击闪白；alpha 通道保持不变。"""
    frame = sprite.copy()
    value = max(0, min(255, round(255 * amount)))
    frame.fill((value, value, value, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return frame


def _data_dir() -> Path:
    """运行时可写数据的存放目录。

    - 源码运行：仓库根目录（与 assets/ 同级），保持原有开发习惯；
    - PyInstaller 打包（--onefile）：可执行文件所在目录，避免写进会被
      清理的 _MEIPASS 临时目录导致存档丢失。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _hiscore_path() -> Path:
    return _data_dir() / config.HISCORE_FILE


def _load_hiscore() -> int:
    try:
        return max(0, int(_hiscore_path().read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        return 0


def _save_hiscore(value: int) -> None:
    try:
        _hiscore_path().write_text(str(value), encoding="utf-8")
    except OSError as exc:
        if getattr(config, "DEBUG_PERSISTENCE", False):
            print(f"[persistence] 最高分写入失败: {exc}")


def _progress_path() -> Path:
    return _data_dir() / config.PROGRESS_FILE


def _load_progress() -> dict:
    """读取关卡解锁进度。返回 ``{"unlocked": 1, "all_cleared": false}``。"""
    try:
        data = json.loads(_progress_path().read_text(encoding="utf-8"))
        return {
            "unlocked": int(data.get("unlocked", 1)),
            "all_cleared": bool(data.get("all_cleared", False)),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"unlocked": 1, "all_cleared": False}


def _save_progress(unlocked: int, all_cleared: bool) -> None:
    try:
        _progress_path().write_text(
            json.dumps({"unlocked": unlocked, "all_cleared": all_cleared},
                       ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        if getattr(config, "DEBUG_PERSISTENCE", False):
            print(f"[persistence] 关卡进度写入失败: {exc}")


class Game:
    """游戏主体：窗口、主循环、输入、碰撞与渲染。"""

    SCENE_TITLE = "title"
    SCENE_CONTROLS = "controls"
    SCENE_STAGE_SELECT = "stage_select"
    SCENE_PLAYING = "playing"
    SCENE_AFTERWORD = "afterword"
    SCENE_CG_GALLERY = "cg_gallery"
    CHEAT_PASSWORD = "472977"          # 作弊模式解锁密码
    ENDING_PAGES = ("result", "afterword", "afterword", "afterword", "credits")
    CREDITS_SCROLL_SECONDS = 10.0      # 謝辞页滚动名单滚完全程所需秒数
    # 人物録页籤顺序：Tab 依次轮转
    GALLERY_TABS = ("人物図鑑", "背景図鑑", "音楽室")
    # 背景図鑑条目：(显示名, 英文/日文副标, 取图键)
    BACKGROUND_GALLERY = (
        ("紅魔館　外観", "SCARLET DEVIL MANSION", "scene"),
        ("紅霧の麓", "STAGE 1  /  FOOTHILLS IN SCARLET MIST", "stage1"),
        ("霧の湖", "STAGE 2  /  MISTY LAKE", "stage2"),
        ("紅魔館　館内", "STAGE 3  /  SCARLET DEVIL MANSION", "stage3"),
        ("異変解決", "ENDING  /  INCIDENT RESOLVED", "victory"),
        ("霊力尽きる", "ENDING  /  INCIDENT UNRESOLVED", "defeat"),
        ("異変のあと", "ENDING  /  AFTER THE INCIDENT", "afterword"),
        ("戦績", "SCORE  /  RESULT", "result"),
        ("標題", "TITLE", "title"),
        ("音楽室", "MUSIC ROOM", "music"),
        ("原作原画 01", "ENDING ILLUSTRATION 01", "roll1"),
        ("原作原画 02", "ENDING ILLUSTRATION 02", "roll2"),
        ("原作原画 03", "ENDING ILLUSTRATION 03", "roll3"),
        ("原作原画 04", "ENDING ILLUSTRATION 04", "roll4"),
        ("原作原画 05", "ENDING ILLUSTRATION 05", "roll5"),
        ("原作原画 06", "ENDING ILLUSTRATION 06", "roll6"),
        ("原作原画 07", "ENDING ILLUSTRATION 07", "roll7"),
        ("原作原画 08", "ENDING ILLUSTRATION 08", "roll8"),
        ("原作原画 09", "ENDING ILLUSTRATION 09", "roll9"),
        ("原作原画 10", "ENDING ILLUSTRATION 10", "roll10"),
    )
    BACKGROUND_PREVIEW_SIZE = (720, 460)
    STAGE_TITLES = ("紅霧の麓", "霧の湖", "紅魔館")
    STAGE_SUBTITLES = (
        "Scarlet Mist  /  Stage 1",
        "Misty Lake  /  Stage 2",
        "Scarlet Devil Mansion  /  Final Stage",
    )
    STAGE_BOSS_NAMES = ("露米婭", "琪露諾", "蕾米莉亞")
    TITLE_INFO_PANEL_RECT = (52, 52, 500, 360)
    MENU_ITEMS = ("开始游戏", "紅霧人物録", "操作说明", "退出游戏")
    MENU_ITEMS_CLEARED = ("开始游戏", "紅霧人物録", "操作说明", "退出游戏", "日后谈")
    # 标题菜单副标题：仿 TH06 原作在日文标题下附英文小字
    MENU_LABELS = {
        "开始游戏": "GAME START",
        "紅霧人物録": "CHARACTER RECORD",
        "操作说明": "MANUAL",
        "退出游戏": "QUIT",
        "日后谈": "AFTERWORD",
    }
    # 说明书分三页：背景 → 用语 → 操作
    MANUAL_PAGES = ("背景说明", "用语解说", "操作指南")

    # 页面一正文：缩进用全角空格，空串表示分段
    MANUAL_STORY = (
        "　　幻想乡，是被遗忘之物栖居的边境之地。",
        "",
        "　　然而这一年的夏天，红雾自湖畔升起。那不是寻常的晚霞，",
        "　而是浓得化不开的绯色，连满月也被浸成血红。人里的灯火",
        "　在雾中熄灭，夜长得望不见尽头。",
        "",
        "　　博丽的巫女循着雾的源头一路追去，行程分成三站。",
        "　先是红雾笼罩的人里近郊，接着是雾气最浓的雾之湖，",
        "　最后是矗立湖畔、掀起整场异变的红魔馆。",
        "",
        "　　每一站都是一场杂兵波次、一位中 Boss、一位关底 Boss。",
        "　躲开绯红的弹雨，逐张符卡破开，",
        "　把这位任性的吸血鬼，从漫长的夜里唤醒吧。",
    )

    # 页面二：世界观与玩法术语
    MANUAL_TERMS = (
        ("幻想乡", "被遗忘之物栖居的边境之地，本作的舞台"),
        ("博丽的巫女", "异变退治者，也就是玩家操纵的自机"),
        ("红魔馆", "矗立湖畔的洋馆，吸血鬼蕾米莉亚的居所"),
        ("关卡 · Stage", "全作三关，每关依次为杂兵波次、中 Boss、关底 Boss"),
        ("符卡 · Spell Card", "东方独有的弹幕规则，一张符卡即一段弹幕式样"),
        ("中 Boss", "波次之后登场的强敌，血量较低，只展开一张符卡"),
        ("关底 Boss", "每关最后的首领，血量高、符卡多，逐张推进"),
        ("弹幕", "符卡铺开的子弹群，全数躲开即为破符"),
        ("自机", "玩家操纵的角色"),
        ("残机", "剩余生命数，本作 3 条，受击减一"),
        ("判定点", "自机唯一的受击点，低速时可见"),
        ("擦弹 · Graze", "敌弹擦过判定点外圈未被击中，可得分"),
        ("灵击 · Spell Card", "消耗一枚符卡，短时无敌并消去身边的弹幕"),
        ("红玉 · POWER", "PWR 标记；拾取即 +0.10 火力，可突破本关成长上限"),
        ("青玉 · POINT", "PTS 标记；得分 +500，是妖精最常见的掉落"),
        ("绿玉 · LIFE", "1UP 标记；残机 +1，稀有妖精或最终符卡掉落"),
    )

    # 页面三：按键表
    MANUAL_KEYS = (
        ("方向键 / WASD", "移动自机"),
        ("Shift", "低速移动，判定点收缩，便于穿过弹缝"),
        ("Z", "点按单发，按住连续射击"),
        ("X", "灵击（Bomb）：消去身边弹幕，短时无敌"),
        ("C", "特殊技能：短蓄力后令全场敌弹减速（时间凝滞）"),
        ("F1", "暂停 / 继续"),
        ("F2", "开关碰撞调试层（判定圆、扫掠线、空间网格）"),
        ("F3", "作弊：输入密码后解锁无敌（再次输入关闭）"),
        ("Tab", "人物录内切换「人物図鑑 / 音楽室」"),
        ("R", "胜负结算后重新开始"),
        ("胜利后 ← / →", "翻阅战绩、后记与鸣谢"),
        ("Enter", "推进对话；胜利后翻页/结束阅读；失败后返回标题"),
        ("Esc", "返回标题；战斗中退出游戏"),
    )
    VICTORY_AFTERWORD_PAGES = (
        (
            "紅霧散去，滿月重新照亮了霧之湖的湖面。",
            "蕾米莉亞仍說，這不過是一場稍有趣味的遊戲，",
            "還抱怨著月亮變回了單調的蒼白色。",
            "",
            "咲夜默默收拾彈痕與碎裂的窗玻璃，",
            "又替主人端來一杯溫熱的紅茶；",
            "美鈴靠在門柱上打盹，帕秋莉則躲回了書架深處。",
            "",
            "「下次，我會準備得更有趣一點。」",
            "吸血鬼的笑聲，隨著紅茶的蒸氣一同消散在夜風裡。",
        ),
        (
            "博麗的巫女沒有收下謝禮，",
            "只確認人里的燈火已重新亮起，便乘風回到神社。",
            "",
            "路上經過霧之湖，冰已化盡，",
            "水面映著滿月，像是什麼都沒發生過。",
            "湖邊的冰之妖精正對著自己的倒影生悶氣，",
            "嘴裡念念有詞地說著「最強」兩個字。",
            "",
            "神社的賽錢箱依舊空空如也——",
            "這件事，倒是從未改變。",
        ),
        (
            "數日之後，紅魔館再度傳出彈幕的聲響。",
            "聽說是館主與圖書館的魔女，為了「紅月亮的最佳觀測角度」",
            "又在院子裡展開了符卡對決。",
            "",
            "人里的孩子們在夕陽下追逐玩耍，",
            "沒有人記得那場被紅霧籠罩的夜晚。",
            "",
            "幻想鄉的異変，大概從來不曾真正完結。",
            "而博麗的巫女，也永遠不會缺下一份工作。",
            "",
            "——紅霧異變，於此落幕。",
        ),
    )
    VICTORY_CREDITS = (
        ("原作", "東方Project / 上海アリス幻樂団"),
        ("音乐", "ZUN"),
        ("曲目来源", "《东方红魔乡》TH06 原作 MIDI"),
        ("素材", "東方紅魔郷（TH06）原作素材"),
        ("制作", "lyra"),
    )
    VICTORY_THANKS = (
        "そして、最後まで遊んでくれた貴方へ。",
        "ありがとう。",
    )

    # 角色图鉴（CG館）：按出场顺序排列。
    # 每条：(立绘键, 显示名, 英文/日文称号, 身份, 介绍段落)
    CG_GALLERY_ENTRIES = (
        (
            "reimu", "博麗靈夢", "Reimu Hakurei",
            "博麗神社的巫女",
            (
                "住在博麗神社的巫女，負責解決幻想鄉的各種異變。",
                "雖然平常看起來有些懶散，實際上彈幕功底紮實，",
                "退治妖怪從不手軟。賽錢箱常年空空如也，",
                "這件事倒是從未改變過。",
            ),
            "靈夢",
        ),
        (
            "rumia", "露米婭", "Rumia",
            "棲息在霧中的黑暗妖怪",
            (
                "操縱黑暗程度的能力的妖怪。",
                "在紅霧彌漫的山麓出沒，以黑暗為掩護偷襲過路人。",
                "個性有些冒失，自稱「最強」的語氣倒是不小，",
                "實力嘛……就當作是夜晚的一點消遣吧。",
            ),
            "露米婭",
        ),
        (
            "cirno", "琪露諾", "Cirno",
            "霧之湖的冰之妖精",
            (
                "住在霧之湖的冰之妖精，自稱「最強」。",
                "能自由操控冰與冷氣，湖面的薄冰便是她的傑作。",
                "個性天真又好勝，最喜歡和過路人較量彈幕。",
                "雖然常常輸，但「最強」二字從未改口。",
            ),
            "琪露諾",
        ),
        (
            "meiling", "紅美鈴", "Hong Meiling",
            "紅魔館的門衛",
            (
                "紅魔館的門衛，中國來的妖怪。",
                "擅長體術與氣功，認真盡責卻常常在值班時打瞌睡。",
                "對闖入者毫不留情，不過偶爾也會放過",
                "看起來不像壞人的客人——雖然事後常被咲夜罵。",
            ),
            "美鈴",
        ),
        (
            "patchouli", "帕秋莉·諾蕾姬", "Patchouli Knowledge",
            "紅魔館圖書館的魔女",
            (
                "紅魔館地下大圖書館的主人，活了百年以上的魔法使。",
                "精通七曜魔法，書庫裡藏著無數禁忌的咒文。",
                "體弱多病，卻能以壓倒性的彈幕量彌補體力的不足。",
                "平時總是埋頭書堆，不太願意見客。",
            ),
            "帕秋莉",
        ),
        (
            "sakuya", "十六夜咲夜", "Sakuya Izayoi",
            "紅魔館的女僕長",
            (
                "紅魔館的女僕長，能操縱時間。",
                "舉止優雅、做事俐落，把整座洋館打理得井然有序。",
                "以小刀為武器，能在一瞬間擲出無數飛刀，",
                "對主人蕾米莉亞絕對忠誠。",
            ),
            "咲夜",
        ),
        (
            "remilia", "蕾米莉亞·斯卡蕾特", "Remilia Scarlet",
            "紅魔館的館主",
            (
                "活了五百年的吸血鬼，紅魔館的館主。",
                "為了看一眼紅色的月亮，用紅霧籠罩了整個幻想鄉。",
                "外表是嬌小的少女，實力卻極為恐怖，",
                "以五張符卡堂堂正正地迎接博麗的巫女。",
            ),
            "蕾米莉亞",
        ),
    )

    # 音楽室：TH06 原作全 17 曲，曲名与 ZUN 评论取自 MD_DAT/musiccmt.txt。
    # 每条：(试听文件, 曲名, 英文名, 评论段落)
    MUSIC_ROOM_TRACKS = (
        ("th06_01.mid", "比赤色更紅的夢", "A Dream More Scarlet than Red", (
            "標題画面的音樂。既然是東方，就試着做成了和風。",
            "明明游戲本身都不像是和風的説；",
            "不過，畢竟是標題画面所必需的曲子。",
        )),
        ("th06_02.mid", "如鬼灯般的紅色之魂", "A Soul as Red as a Ground Cherry", (
            "第１面的音樂。想要突出夜晚森林的印象。",
            "與其說給人勇氣感，",
            "還不如說是有趣的百鬼夜行吧？",
        )),
        ("th06_03.mid", "妖魔夜行", "Apparitions Stalk the Night", (
            "露米婭的音樂。表現夜晚的妖怪的印象。",
            "不僅是這首音樂，總的來說這次的音樂都變得輕快了。",
            "總的來說，是有些笨蛋的感覺。",
        )),
        ("th06_04.mid", "錯亂的妖精", "Lunate Elf", (
            "第２面的音樂。",
            "有水和霧的印象，試着混入了些可怕的感覺。",
            "雖説是第２面，卻不清楚到底為什麼而存在。",
        )),
        ("th06_05.mid", "活潑的純情小姑娘", "Beloved Tomboyish Girl", (
            "琪露諾的音樂。",
            "果然，作成了有些笨的少女的印象。",
            "以高速度的旋律爲主。算了，反正是第２面啦。",
        )),
        ("th06_06.mid", "上海紅茶館 ～ Chinese Tea", "Shanghai Teahouse ～ Chinese Tea", (
            "第３面的音樂。雖然打算作成中華風，結果好像不是這樣。",
            "不過音樂是東洋風；",
            "與其說是 Fusion，不如說是 New Age 風吧？",
        )),
        ("th06_07.mid", "明治17年的上海愛麗絲", "Shanghai Alice of Meiji 17", (
            "紅美鈴的音樂。",
            "歐羅巴的香味和遊戲音樂的香味混合在一起。（2：8 左右）",
            "以上海的法國租界為印象。",
        )),
        ("th06_08.mid", "巴瓦魯魔法圖書館", "Voile, the Magic Library", (
            "第４面的音樂。從這關開始就是室內的場地。",
            "後半，中 Boss 左右曲調開始變得有點可怕。",
            "要說特徵的話——不像是ＳＴＧ的曲子（笑）",
        )),
        ("th06_09.mid", "封閉的少女 ～ 少女密室", "Locked Girl ～ The Girl's Secret Room", (
            "帕秋莉·諾蕾姬的音樂。",
            "有點陰暗的曲子。節奏激烈卻沒有明快的感覺。",
            "聽了這首曲子就會感受到那微妙陰暗的氣息（笑）",
        )),
        ("th06_10.mid", "女僕和血的懷錶", "The Maid and the Pocket Watch of Blood", (
            "第５面的音樂。不可思議的不可思議之曲。",
            "本想讓曲子充滿速度感，結果卻給人一種搖搖欲墜的感覺，",
            "是不是因為使用了特殊的節拍的緣故呢？",
        )),
        ("th06_11.mid", "月時計 ～ 月的鐘錶盤", "Lunar Clock ～ Luna Dial", (
            "十六夜·咲夜的音樂。",
            "說起女僕就是要重搖滾（假的）。",
            "……果然是誤解了搖滾的定义吧（^^；",
        )),
        ("th06_12.mid", "TEPES的年輕末裔", "The Young Descendant of Tepes", (
            "最終關的音樂。",
            "最終關一向都是比較寧靜的，所以這次採用了輕快的風格。",
            "只是短短的關卡裏用來連接的曲子。",
        )),
        ("th06_13.mid", "為死亡的公主所奏的七重奏", "Septette for the Dead Princess", (
            "蕾米利亞·斯卡蕾特的音樂。這就是最後了！",
            "因為不喜歡那樣厚重和令人不快的最終關，",
            "融合了爵士乐風格和蘿莉的要素——就和平時一樣了。",
        )),
        ("th06_14.mid", "魔法少女們的百年祭典", "The Centennial Festival for Magical Girls", (
            "ＥＸ關的音樂。有時是中華風，有時是 New Age 風格。",
            "也沒去想什麼主題，就在鍵盤上这样彈出来了。",
            "像是集我的惰性於大成的曲子。",
        )),
        ("th06_15.mid", "U.N.OWEN就是她嗎？", "U.N. Owen Was Her?", (
            "芙蘭多露·斯卡蕾特的音樂。這次最喜歡的音樂。",
            "挑戰是否能表現出神秘的結果。",
            "用鍵盤演奏很有趣。",
        )),
        ("th06_16.mid", "比紅色更虛無的永遠", "A Dream More Transient than Scarlet", (
            "結局的音樂。",
            "從曲名就可以想像出，是像片頭一樣編曲的東西。",
            "所以用了和風——或者說，和風的音樂都不错吧。",
        )),
        ("th06_17.mid", "紅樓 ～ Eastern Dream．．．", "Crimson Belvedere ～ Eastern Dream...", (
            "製作人員表的音樂。",
            "前作製作人員表的音樂一直都是絕望陰暗的調子，",
            "但這次變成了充满希望而明快的曲子了……大概吧。",
        )),
    )
    MUSIC_ROOM_VISIBLE = 12         # 音楽室列表一屏可显示的曲目数

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
        pygame.key.stop_text_input()
        pygame.display.set_caption("东方红雾录 · 红雾异变")
        # 窗口/任务栏图标：与打包用的 icon.ico 同源，取自东方角色（博丽灵梦）立绘
        pygame.display.set_icon(
            pygame.image.load(
                str(Path(__file__).resolve().parent.parent / "assets" / "icon.png")
            )
        )
        self.clock = pygame.time.Clock()
        self.font = _load_font(24)
        self.font_big = _load_font(42)
        self.font_menu = _load_font(32)      # 标题菜单主文字（仿原作大字）
        self.font_small = _load_font(18)     # 菜单英文副标与音楽室曲目列表
        self.art = GameArt()
        self.audio = Audio()
        asset_dir = Path(__file__).resolve().parent.parent / "assets" / "title"
        title_background = pygame.image.load(
            str(asset_dir / "touhou-th06-title.jpg")
        )
        self.title_background = pygame.transform.smoothscale(
            title_background, (config.SCREEN_W, config.SCREEN_H)
        )
        self.title_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.title_shade.fill((7, 3, 9, 112))
        self.entry_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.entry_shade.fill((5, 2, 8, 168))
        self.ending_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.ending_shade.fill((7, 3, 9, 168))
        # 后记文字页用更轻的压暗层：卡片半透明，让原作插图透出来
        self.ending_light_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.ending_light_shade.fill((7, 3, 9, 86))

        # 音楽室背景：TH06 原作 TL_DAT/music.jpg，右上角标题区域留白较多，
        # 正好用来铺曲目列表与 ZUN 评论。
        self.music_room_background = pygame.transform.smoothscale(
            pygame.image.load(str(asset_dir / "music-room.jpg")),
            (config.SCREEN_W, config.SCREEN_H),
        )
        self.music_room_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.music_room_shade.fill((7, 3, 9, 96))   # 轻压暗，保留原作背景细节

        # 关卡选择背景：TH06 原作选关画面 TL_DAT/select00.jpg，比标题图更贴合
        # 「选择关卡」的语境；面板半透明，让原作背景透出来。
        self.stage_select_background = pygame.transform.smoothscale(
            pygame.image.load(str(asset_dir / "stage-select.jpg")),
            (config.SCREEN_W, config.SCREEN_H),
        )
        self.stage_select_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.stage_select_shade.fill((7, 3, 9, 104))
        # 人物録 / 背景図鑑共用一层稍轻的压暗：内容卡片已重压暗，背景只需微调
        self.gallery_shade = pygame.Surface(
            (config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA
        )
        self.gallery_shade.fill((7, 3, 9, 138))

        # 謝辞滚动用的原作结局插画（ED_DAT），与名单一起自下而上轮播
        scene_dir = asset_dir.parent / "scene"
        self.credits_roll_images = tuple(
            pygame.transform.smoothscale(
                pygame.image.load(str(scene_dir / f"ending-roll-{index}.jpg")),
                (config.SCREEN_W, config.SCREEN_H),
            )
            for index in range(1, 11)
        )
        # 背景図鑑：进入时一次性裁好预览图，避免每帧缩放
        self.background_gallery = tuple(
            (name, english,
             _cover_scale(self._background_surface(key),
                          self.BACKGROUND_PREVIEW_SIZE))
            for name, english, key in self.BACKGROUND_GALLERY
        )

        self.running = True
        self.scene = self.SCENE_TITLE
        self.menu_selection = 0
        self.stage_select_index = 0      # 关卡选择界面当前选中的关卡（0 起）
        self.unlocked_stage = 1          # 已解锁的最高关卡序号（1 起，默认第 1 关）
        self.all_cleared = False         # 是否通关全部关卡（解锁日后谈）
        self.afterword_only = False      # 是否从菜单单独进入日后谈
        self.cg_gallery_index = 0        # 角色图鉴当前选中角色（0 起）
        self.cg_detail_active = False    # 是否进入角色详情页（查看多张 CG）
        self.cg_detail_cg_index = 0      # 详情页中当前查看的 CG 索引
        self.cg_tab = 0                  # 人物録内页籤：0=人物図鑑，1=背景図鑑，2=音楽室
        self.cg_background_index = 0     # 背景図鑑当前查看的画面（0 起）
        self.music_room_index = 0        # 音楽室当前选中的曲目（0 起）
        self.music_room_scroll = 0       # 曲目列表滚动偏移（首行序号）
        self.music_preview = None        # 正在试听的曲目文件名，None 表示未试听
        self.credits_time = 0.0          # 謝辞滚动已播放的秒数
        self._credits_active = False     # 上一帧是否停在謝辞页（用于重置滚动）
        self.quit_confirm_active = False  # 标题菜单是否弹出「退出游戏」确认框
        self.quit_confirm_index = 1       # 确认框选项：0=是，1=否（默认停在否）
        # 退出确认框的用途："quit" = 关闭程序，"title" = 返回标题
        self.quit_confirm_action = "quit"
        progress = _load_progress()
        self.unlocked_stage = progress["unlocked"]
        self.all_cleared = progress["all_cleared"]
        self.manual_page = 0          # 说明书当前页：背景 / 用语 / 操作
        self.ending_page = 0
        self.paused = False
        self.god_mode = False
        self.cheat_prompt_active = False    # 是否正在输入作弊密码
        self.cheat_input = ""               # 当前已输入的密码字符
        self.victory = False
        self.game_over = False
        self.lives = config.PLAYER_LIVES
        self.invulnerable_timer = 0.0
        self.focus = False            # 是否处于低速（focus）状态，由 update 写入
        self.bombs = config.PLAYER_BOMB_START   # 灵击（Bomb）存量
        self.bomb_timer = 0.0                   # 灵击无敌/清弹剩余时间
        self.bomb_charge = 0.0                  # 充能累加，满 PLAYER_BOMB_RECHARGE 回复 1 枚
        # 自机特殊技能：ready → charge（短蓄力）→ recover（后摇）；蓄力不会被击断
        self.skill_state = "ready"
        self.skill_timer = 0.0                  # 当前阶段的剩余时间
        self.bullet_slow_timer = 0.0            # 敌弹减速（时间凝滞）剩余时间

        self.player = Player(
            config.PLAYER_START_X, config.PLAYER_START_Y
        )
        # 关卡推进交给 director；Boss 只在对局中出现，未开打时为 None
        self.director = StageDirector()
        self.boss: Boss | None = None
        self.bullets: list[Bullet] = []
        self.boss_beams: list[BossBeam] = []
        self.player_shots: list[PlayerShot] = []
        self.fairies: list[Fairy] = []
        self.fairy_kill_count = 0
        self.items: list[Item] = []
        # 空间网格复用同一个实例，每帧 clear 后重新插入，避免反复新建
        self.grid = collision.SpatialGrid(config.SCREEN_W, config.SCREEN_H,
                                          config.GRID_CELL_SIZE)
        self.shooting = False
        self.shoot_requested = False
        self.fire_timer = 0.0
        self.boss_attack_phase = 0          # 当前符卡序号，用于检测换段
        self.spell_timers: list[float] = []  # 各发射器的独立冷却
        self.spell_imperilled = False        # 当前符卡期间是否被击中 / 用过灵击
        self.spell_timed_out = False         # 当前符卡是否因超时结束
        self.spells_captured = 0             # 成功取得的符卡数
        self.spells_failed = 0               # 失败（被击中 / 灵击 / 超时）的符卡数
        self.awarded_clear = 0               # 已发放通关奖励的关卡序号
        self.spell_announce_timer = 0.0      # 符卡名与技能描述的播报倒计时
        self.graze_total = 0
        self.hit_total = 0
        self.hit_flash = 0.0          # 命中时的红屏闪烁计时
        self.animation_timer = 0.0
        self.playfield_shade = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT), pygame.SRCALPHA
        )
        self.playfield_shade.fill((7, 3, 9, 52))
        self.panel_shade = pygame.Surface(
            (416, config.PLAYFIELD_HEIGHT), pygame.SRCALPHA
        )
        self.panel_shade.fill((*config.PANEL, 222))
        self.hit_overlay = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT), pygame.SRCALPHA
        )
        self.hit_overlay.fill((150, 12, 30, 80))
        # 时间凝滞期间的冷色蒙版，提示敌弹已被放慢
        self.slow_overlay = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT), pygame.SRCALPHA
        )
        self.slow_overlay.fill((70, 140, 230, 40))
        self.debug_overlay = config.DEBUG_OVERLAY_DEFAULT
        self.debug_stats = self._empty_debug_stats()

        # 计分与战斗节奏
        self.score = 0
        self.hiscore = _load_hiscore()
        self.power = config.PLAYER_POWER_START   # 火力：关卡保底 + 时间成长 + 红玉
        self.power_time = 0.0                     # 时间成长的累加器
        self.power_up_timer = 0.0                 # 「火力上昇」提示剩余时间
        self.power_up_text = ""                   # 提示文案（升档时写入）
        self.item_total = 0                       # 本局已拾取道具数
        self.effects: list[Effect] = []
        self.phase_timer = config.BOSS_PHASE_TIME_LIMIT
        self.boss_flash = 0.0            # Boss 受击闪白计时
        self.graze_fx_cooldown = 0.0     # 擦弹特效的节流，避免刷屏
        self.boss_ceremony_timer = 0.0   # 最终 Boss 击破仪式的剩余时间
        self.screen_shake = 0.0          # 屏幕震动幅度（像素）
        # Boss 特殊技能：按血量比例分档发动，越低血量越频繁；蓄力 → 释放 → 后摇
        self.boss_skill_next_hp = config.BOSS_SKILL_FIRST_HP  # 下次发动需跌破的血量比例
        self.boss_skill_timer = 0.0      # 蓄力剩余时间（>0 表示正在蓄力）
        self.boss_skill_recover = 0.0    # 后摇剩余时间（玩家的反击窗口）
        self.boss_skill_announce_timer = 0.0   # 技能名播报倒计时
        self.boss_skill_announce_name = ""
        # Boss 特殊技能释放瞬间的全屏闪光
        self.skill_flash = 0.0
        self.skill_overlay = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT), pygame.SRCALPHA
        )
        self.skill_overlay.fill((255, 236, 212))
        self.field_vignette = _build_vignette(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT)
        )

    @staticmethod
    def _empty_debug_stats() -> dict[str, int]:
        """当帧碰撞统计，供调试层显示；每帧开始时清零。"""
        return {
            "candidates": 0,   # 宽相位候选数
            "sweeps": 0,       # 玩家弹参与扫掠的次数
            "hits": 0,         # 玩家被命中次数
            "grazes": 0,       # 本帧新增擦弹次数
            "boss_sweeps": 0,  # 玩家弹对 Boss 的扫掠次数
            "boss_hits": 0,    # 玩家弹命中 Boss 次数
        }

    # ------------------------------------------------------------------ #
    # 输入
    # ------------------------------------------------------------------ #
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _menu_items(self) -> tuple[str, ...]:
        """根据通关状态返回标题菜单项（通关后追加「日后谈」）。"""
        return self.MENU_ITEMS_CLEARED if self.all_cleared else self.MENU_ITEMS

    def _handle_quit_confirm_key(self, key: int) -> None:
        """退出确认框：左右切换「是 / 否」，Enter 确定，Esc 取消。"""
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d,
                   pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            self.quit_confirm_index = 1 - self.quit_confirm_index
            self.audio.play("menu_move")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.quit_confirm_index == 0:
                if self.quit_confirm_action == "title":
                    # 放弃本局：回到标题界面，而不是关闭程序
                    self._abandon_run_to_title()
                else:
                    self.running = False
            else:
                self.quit_confirm_active = False
                self.audio.play("menu_cancel")
        elif key == pygame.K_ESCAPE:
            self.quit_confirm_active = False
            self.audio.play("menu_cancel")

    def _abandon_run_to_title(self) -> None:
        """放弃当前这一局，回到标题界面。"""
        self.quit_confirm_active = False
        self.paused = False
        self.scene = self.SCENE_TITLE
        self.menu_selection = 0
        # 标题界面的背景音乐会由 _update_music() 在下一帧自动接回
        self.audio.stop_music()
        self.audio.play("menu_cancel")

    def _handle_background_gallery_key(self, key: int) -> None:
        """背景図鑑：方向键翻阅原作背景与结局插画。"""
        total = len(self.background_gallery)
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
            if self.cg_background_index > 0:
                self.cg_background_index -= 1
                self.audio.play("menu_move")
        elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
            if self.cg_background_index < total - 1:
                self.cg_background_index += 1
                self.audio.play("menu_move")
        elif key == pygame.K_ESCAPE:
            self.audio.play("menu_cancel")
            self.scene = self.SCENE_TITLE

    def _on_credits_page(self) -> bool:
        """当前是否停在謝辞滚动页（日后谈与通关流程的最后页）。"""
        browsing = self.scene == self.SCENE_AFTERWORD
        clearing = self.scene == self.SCENE_PLAYING and self.victory
        if not (browsing or clearing):
            return False
        return getattr(self, "ending_page", 0) >= len(self.ENDING_PAGES) - 1

    def _advance_credits_roll(self, dt: float) -> None:
        """在謝辞页累加滚动计时；翻到该页时从头开始，滚完停在末页等 Enter。"""
        on_credits = self._on_credits_page()
        if on_credits and not getattr(self, "_credits_active", False):
            self.credits_time = 0.0     # 刚翻到謝辞页：名单从页首重新滚
        self._credits_active = on_credits
        if on_credits:
            self.credits_time = min(
                self.CREDITS_SCROLL_SECONDS, self.credits_time + dt
            )

    def _credits_roll_finished(self) -> bool:
        """謝辞名单是否已滚完（滚完前 Enter 不生效，避免漏看名单）。"""
        return getattr(self, "credits_time", 0.0) >= self.CREDITS_SCROLL_SECONDS

    def _clamp_music_scroll(self) -> None:
        """让滚动窗口跟随当前选中曲目，保证它始终落在可视范围内。"""
        total = len(self.MUSIC_ROOM_TRACKS)
        visible = self.MUSIC_ROOM_VISIBLE
        if self.music_room_index < self.music_room_scroll:
            self.music_room_scroll = self.music_room_index
        elif self.music_room_index >= self.music_room_scroll + visible:
            self.music_room_scroll = self.music_room_index - visible + 1
        self.music_room_scroll = max(0, min(self.music_room_scroll,
                                            max(0, total - visible)))

    def _handle_music_room_key(self, key: int) -> None:
        """音楽室：上下选曲、Enter 试听、Esc 返回标题（Tab 由外层处理）。"""
        total = len(self.MUSIC_ROOM_TRACKS)
        if key in (pygame.K_UP, pygame.K_w):
            if self.music_room_index > 0:
                self.music_room_index -= 1
                self._clamp_music_scroll()
                self.audio.play("menu_move")
        elif key in (pygame.K_DOWN, pygame.K_s):
            if self.music_room_index < total - 1:
                self.music_room_index += 1
                self._clamp_music_scroll()
                self.audio.play("menu_move")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            filename = self.MUSIC_ROOM_TRACKS[self.music_room_index][0]
            if self.audio.play_file(filename):
                self.music_preview = filename
                self.audio.play("menu_ok")
            else:
                self.audio.play("menu_cancel")
        elif key == pygame.K_ESCAPE:
            self.audio.play("menu_cancel")
            self.music_preview = None
            self.scene = self.SCENE_TITLE
            self.menu_selection = 0

    def _handle_keydown(self, key: int) -> None:
        # 退出确认框优先处理：无论处在标题还是关卡内都先走确认框逻辑
        if getattr(self, "quit_confirm_active", False):
            self._handle_quit_confirm_key(key)
            return
        if self.scene == self.SCENE_TITLE:
            items = self._menu_items()
            if key == pygame.K_UP:
                self.menu_selection = (self.menu_selection - 1) % len(items)
                self.audio.play("menu_move")
            elif key == pygame.K_DOWN:
                self.menu_selection = (self.menu_selection + 1) % len(items)
                self.audio.play("menu_move")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                label = items[self.menu_selection]
                if label == "退出游戏":
                    # 先弹确认框，避免误触直接关闭
                    self.quit_confirm_action = "quit"
                    self.quit_confirm_active = True
                    self.quit_confirm_index = 1     # 默认停在「否」
                    self.audio.play("menu_move")
                    return
                self.audio.play("menu_ok")
                if label == "开始游戏":
                    self.stage_select_index = 0
                    self.scene = self.SCENE_STAGE_SELECT
                elif label == "操作说明":
                    self.manual_page = 0
                    self.scene = self.SCENE_CONTROLS
                elif label == "日后谈":
                    self.afterword_only = True
                    self.ending_page = 1       # 从后记页开始翻阅
                    self.scene = self.SCENE_AFTERWORD
                elif label == "紅霧人物録":
                    self.cg_gallery_index = 0
                    self.cg_detail_active = False
                    self.cg_tab = 0
                    self.cg_background_index = 0
                    self.music_preview = None
                    self.scene = self.SCENE_CG_GALLERY
            elif key == pygame.K_ESCAPE:
                # Esc 与「退出游戏」同义：同样先确认
                self.quit_confirm_action = "quit"
                self.quit_confirm_active = True
                self.quit_confirm_index = 1
                self.audio.play("menu_move")
            return

        if self.scene == self.SCENE_STAGE_SELECT:
            if key == pygame.K_UP:
                self.stage_select_index = max(0, self.stage_select_index - 1)
                self.audio.play("menu_move")
            elif key == pygame.K_DOWN:
                self.stage_select_index = min(
                    config.STAGE_COUNT - 1, self.stage_select_index + 1
                )
                self.audio.play("menu_move")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.stage_select_index < self.unlocked_stage:
                    self.audio.play("menu_ok")
                    self._reset_run(self.stage_select_index)
                    self.scene = self.SCENE_PLAYING
                else:
                    self.audio.play("menu_cancel")
            elif key == pygame.K_ESCAPE:
                self.audio.play("menu_cancel")
                self.scene = self.SCENE_TITLE
                self.menu_selection = 0
            return

        if self.scene == self.SCENE_AFTERWORD:
            # 日后谈独立翻阅：沿用 ending_page，覆盖 result/afterword/credits 三页
            min_page = 1 if getattr(self, "afterword_only", False) else 0
            if key in (pygame.K_LEFT, pygame.K_a):
                if self.ending_page > min_page:
                    self.ending_page -= 1
                    self.audio.play("menu_move")
            elif key in (pygame.K_RIGHT, pygame.K_d):
                if self.ending_page < len(self.ENDING_PAGES) - 1:
                    self.ending_page += 1
                    self.audio.play("menu_move")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.ending_page < len(self.ENDING_PAGES) - 1:
                    self.ending_page += 1
                    self.audio.play("menu_ok")
                elif self._credits_roll_finished():
                    self.audio.play("menu_cancel")
                    self.afterword_only = False
                    self.scene = self.SCENE_TITLE
                # 名单还在滚：Enter 不生效，等滚完再退出
            elif key == pygame.K_ESCAPE:
                self.audio.play("menu_cancel")
                self.afterword_only = False
                self.scene = self.SCENE_TITLE
            return

        if self.scene == self.SCENE_CONTROLS:
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.audio.play("menu_cancel")
                self.scene = self.SCENE_TITLE
            elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                step = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
                page = min(max(self.manual_page + step, 0), len(self.MANUAL_PAGES) - 1)
                if page != self.manual_page:
                    self.manual_page = page
                    self.audio.play("menu_move")
            return

        if self.scene == self.SCENE_CG_GALLERY:
            if key == pygame.K_TAB:
                # 人物図鑑 → 背景図鑑 → 音楽室 轮转；离开音楽室时停止试听
                self.cg_tab = (self.cg_tab + 1) % len(self.GALLERY_TABS)
                self.music_preview = None
                self.audio.play("menu_move")
                return
            if self.cg_tab == 2:
                self._handle_music_room_key(key)
                return
            if self.cg_tab == 1:
                self._handle_background_gallery_key(key)
                return
            total = len(self.CG_GALLERY_ENTRIES)
            if self.cg_detail_active:
                # 详情页：← → 切换该角色的多张 CG，Esc 返回列表
                entry = self.CG_GALLERY_ENTRIES[self.cg_gallery_index]
                portrait_group = self.art.portraits.get(entry[0])
                cg_count = len(portrait_group) if portrait_group else 1
                if key in (pygame.K_LEFT, pygame.K_a):
                    if self.cg_detail_cg_index > 0:
                        self.cg_detail_cg_index -= 1
                        self.audio.play("menu_move")
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    if self.cg_detail_cg_index < cg_count - 1:
                        self.cg_detail_cg_index += 1
                        self.audio.play("menu_move")
                elif key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.cg_detail_active = False
                    self.cg_detail_cg_index = 0
                    self.audio.play("menu_cancel")
            else:
                # 列表页：← → 切换角色，Enter 进入详情页
                if key in (pygame.K_LEFT, pygame.K_a):
                    if self.cg_gallery_index > 0:
                        self.cg_gallery_index -= 1
                        self.audio.play("menu_move")
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    if self.cg_gallery_index < total - 1:
                        self.cg_gallery_index += 1
                        self.audio.play("menu_move")
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.cg_detail_active = True
                    self.cg_detail_cg_index = 0
                    self.audio.play("menu_ok")
                elif key == pygame.K_ESCAPE:
                    self.audio.play("menu_cancel")
                    self.scene = self.SCENE_TITLE
            return

        if self.game_over:
            if key == pygame.K_r:
                self._reset_run()
            elif key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.audio.play("menu_cancel")
                self.game_over = False
                self.scene = self.SCENE_TITLE
                self.menu_selection = 0
            return

        if self.victory:
            if key == pygame.K_r:
                self._reset_run()
            elif key in (pygame.K_LEFT, pygame.K_a):
                if self.ending_page > 0:
                    self.ending_page -= 1
                    self.audio.play("menu_move")
            elif key in (pygame.K_RIGHT, pygame.K_d):
                if self.ending_page < len(self.ENDING_PAGES) - 1:
                    self.ending_page += 1
                    self.audio.play("menu_move")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.ending_page < len(self.ENDING_PAGES) - 1:
                    self.ending_page += 1
                    self.audio.play("menu_ok")
                elif self._credits_roll_finished():
                    self.audio.play("menu_cancel")
                    self.victory = False
                    self.scene = self.SCENE_TITLE
                    self.menu_selection = 0
                # 名单还在滚：Enter 不生效，等滚完再退出
            elif key == pygame.K_ESCAPE:
                self.audio.play("menu_cancel")
                self.victory = False
                self.scene = self.SCENE_TITLE
                self.menu_selection = 0
            return

        # 作弊密码输入中：优先处理，Esc 只关闭输入框，不会直接退出游戏
        if getattr(self, "cheat_prompt_active", False):
            if pygame.K_0 <= key <= pygame.K_9:
                self.cheat_input += chr(key)
                self.audio.play("menu_move")
                if len(self.cheat_input) >= len(self.CHEAT_PASSWORD):
                    if self.cheat_input == self.CHEAT_PASSWORD:
                        self.god_mode = not self.god_mode
                        self.audio.play("menu_ok")
                    else:
                        self.audio.play("menu_cancel")
                    self.cheat_prompt_active = False
                    self.cheat_input = ""
            elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.cheat_prompt_active = False
                self.cheat_input = ""
                self.audio.play("menu_cancel")
            return
        if key == pygame.K_ESCAPE:
            # 关卡内退出先弹确认框，确认后返回标题，不直接关闭程序
            self.quit_confirm_action = "title"
            self.quit_confirm_active = True
            self.quit_confirm_index = 1     # 默认停在「否」
            self.audio.play("menu_move")
            return
        director = getattr(self, "director", None)
        if director is not None and director.waiting_dialogue:
            # 对话进行中：Z / Enter / 空格 先补全本行，再推进到下一句
            if key in (pygame.K_z, pygame.K_RETURN, pygame.K_KP_ENTER,
                       pygame.K_SPACE):
                self.audio.play("menu_move")
                director.advance_dialogue()
            return
        if key == pygame.K_z:
            self.shoot_requested = True
        elif key == pygame.K_x:
            self._use_bomb()
        elif key == pygame.K_c:
            self._use_player_skill()
        elif key == pygame.K_F1:
            self.paused = not self.paused
        elif key == pygame.K_F2:
            self.debug_overlay = not self.debug_overlay
        elif key == pygame.K_F3:
            # F3：已开启无敌时直接关闭；未开启时弹出密码输入框
            if getattr(self, "god_mode", False):
                self.god_mode = False
                self.audio.play("menu_cancel")
            else:
                self.cheat_prompt_active = True
                self.cheat_input = ""
                self.audio.play("menu_ok")
            return

    def _read_player_input(self) -> tuple[bool, bool]:
        """读取玩家移动、低速和射击输入。"""
        keys = pygame.key.get_pressed()
        move = Vector2(0.0, 0.0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move.x -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move.x += 1.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move.y -= 1.0
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move.y += 1.0

        focus = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        if move.length_squared() > 0:
            move = move.normalize()
        speed = config.PLAYER_SPEED * (config.PLAYER_FOCUS_FACTOR if focus else 1.0)
        self.player.vel = move * speed
        shooting = bool(keys[pygame.K_z] or self.shoot_requested)
        return focus, shooting

    # ------------------------------------------------------------------ #
    # 逻辑更新
    # ------------------------------------------------------------------ #
    def _power_tier(self) -> int:
        return battle._power_tier(self)

    def _shot_offsets(self) -> tuple[float, ...]:
        return battle._shot_offsets(self)

    def _player_shot_sprite(self) -> pygame.Surface:
        return battle._player_shot_sprite(self)

    def _player_shot_trail(self) -> pygame.Surface:
        return battle._player_shot_trail(self)

    def _power_stage_curve(self) -> tuple[float, float]:
        return battle._power_stage_curve(self)

    def _update_power_growth(self, dt: float) -> None:
        return battle._update_power_growth(self, dt)

    def _add_power(self, amount: float, cap: float | None = None) -> None:
        return battle._add_power(self, amount, cap)

    def _spawn_player_shots(self, dt: float) -> None:
        return battle._spawn_player_shots(self, dt)

    def _boss_attack_origin(self, boss: Boss) -> Vector2:
        return battle._boss_attack_origin(self, boss)

    def _spawn_boss(self, spec) -> None:
        return battle._spawn_boss(self, spec)

    def _spawn_boss_attack(self, boss: Boss, emitter) -> None:
        return battle._spawn_boss_attack(self, boss, emitter)

    def _update_boss_attacks(self, dt: float) -> None:
        return battle._update_boss_attacks(self, dt)

    def _update_boss_skill(self, dt: float) -> bool:
        return battle._update_boss_skill(self, dt)

    def _release_boss_skill(self, boss: Boss, special) -> None:
        return battle._release_boss_skill(self, boss, special)

    def _enter_spell(self, boss: Boss, spell, remaining: float) -> None:
        return battle._enter_spell(self, boss, spell, remaining)

    def _settle_spell(self, remaining: float) -> None:
        return battle._settle_spell(self, remaining)

    def _force_phase_end(self) -> None:
        return battle._force_phase_end(self)

    def _check_boss_collisions(self) -> None:
        return battle._check_boss_collisions(self)

    def _check_fairy_collisions(self) -> None:
        return battle._check_fairy_collisions(self)

    def _on_fairy_defeated(self, fairy: Fairy) -> None:
        return battle._on_fairy_defeated(self, fairy)

    def _spawn_items(self, x: float, y: float, kind: str, count: int) -> None:
        return battle._spawn_items(self, x, y, kind, count)

    def _collect_item(self, item: Item) -> None:
        return battle._collect_item(self, item)

    def _update_items(self, dt: float) -> None:
        return battle._update_items(self, dt)

    def _on_boss_defeated(self) -> None:
        return battle._on_boss_defeated(self)

    def _register_hiscore(self) -> None:
        """刷新并持久化最高分（无写权限时静默忽略）。"""
        if self.score > self.hiscore:
            self.hiscore = self.score
            _save_hiscore(self.hiscore)

    def _reset_run(self, stage_index: int = 0) -> None:
        """从头开始一局：复位 director 与全部战斗状态。

        ``stage_index`` 为 0 起的关卡序号，决定从哪一关开始；关卡选择界面
        据此让玩家重玩已解锁的任意一关。
        """
        self.player = Player(config.PLAYER_START_X, config.PLAYER_START_Y)
        self.boss = None
        self.bullets.clear()
        self.boss_beams.clear()
        self.player_shots.clear()
        self.grid.clear()
        self.shooting = False
        self.shoot_requested = False
        self.fire_timer = 0.0
        self.boss_attack_phase = 0
        self.spell_timers = []
        self.spell_imperilled = False
        self.spell_timed_out = False
        self.spells_captured = 0
        self.spells_failed = 0
        self.awarded_clear = 0
        self.spell_announce_timer = 0.0
        self.graze_total = 0
        self.hit_total = 0
        self.hit_flash = 0.0
        self.score = 0                 # 单局分数重置，最高分保留
        # 关卡保底火力：重玩后面的关直接从前一关的成长上限起步
        stage_index = min(max(0, stage_index), len(config.POWER_STAGE_CURVE) - 1)
        self.power = config.POWER_STAGE_CURVE[stage_index][0]
        self.power_time = 0.0
        self.power_up_timer = 0.0
        self.item_total = 0
        self.effects.clear()
        self.items.clear()
        self.fairies.clear()
        self.fairy_kill_count = 0
        self.phase_timer = config.BOSS_PHASE_TIME_LIMIT
        self.boss_flash = 0.0
        self.graze_fx_cooldown = 0.0
        self.boss_ceremony_timer = 0.0
        self.screen_shake = 0.0
        self.lives = config.PLAYER_LIVES
        self.invulnerable_timer = 0.0
        self.bombs = config.PLAYER_BOMB_START
        self.bomb_timer = 0.0
        self.bomb_charge = 0.0
        self.skill_state = "ready"
        self.skill_timer = 0.0
        self.bullet_slow_timer = 0.0
        self.boss_skill_next_hp = config.BOSS_SKILL_FIRST_HP
        self.boss_skill_timer = 0.0
        self.boss_skill_recover = 0.0
        self.boss_skill_announce_timer = 0.0
        self.skill_flash = 0.0
        self.focus = False
        self.paused = False
        self.victory = False
        self.ending_page = 0
        self.game_over = False
        self.scene = self.SCENE_PLAYING
        self.animation_timer = 0.0
        self.director = StageDirector(start_stage=stage_index)
        self.director.reset()
        self.director.start()

    def _use_bomb(self) -> None:
        return battle._use_bomb(self)

    def _recharge_bombs(self, dt: float) -> None:
        return battle._recharge_bombs(self, dt)

    def _use_player_skill(self) -> None:
        return battle._use_player_skill(self)

    def _release_player_skill(self) -> None:
        return battle._release_player_skill(self)

    def _update_player_skill(self, dt: float) -> None:
        return battle._update_player_skill(self, dt)

    def _decay_screen_shake(self, dt: float, rate: float | None = None) -> None:
        return battle._decay_screen_shake(self, dt, rate)

    def _check_collisions(self) -> None:
        return battle._check_collisions(self)

    def _on_player_hit(self, bullet: Bullet | None) -> None:
        return battle._on_player_hit(self, bullet)

    def _advance_effects(self, dt: float) -> None:
        return battle._advance_effects(self, dt)

    def _update_fairies(self, dt: float) -> None:
        return battle._update_fairies(self, dt)

    def _update_music(self) -> None:
        """按当前场景与流程状态切换循环背景音乐；同一首不会被打断重来。

        每个关卡与每个 Boss 都有独立的 TH06 原作曲目；若 MIDI 不可用则
        自动降级到旧版 PC-98 OGG。
        """
        if self.scene == self.SCENE_STAGE_SELECT:
            self.audio.play_music("stage_select")
            return
        if self.scene in (self.SCENE_TITLE, self.SCENE_CONTROLS):
            self.audio.play_music("title")
            return
        if self.scene == self.SCENE_CG_GALLERY:
            if getattr(self, "music_preview", None):
                return          # 音楽室试听中：不覆盖试听曲目
            self.audio.play_music("ending")
            return
        if self.scene == self.SCENE_AFTERWORD:
            if getattr(self, "ending_page", 0) >= len(self.ENDING_PAGES) - 1:
                self.audio.play_music("credits")
            else:
                self.audio.play_music("ending")
            return
        if self.scene != self.SCENE_PLAYING:
            return
        if self.victory:
            # 胜利流程：afterword 用结局曲，credits 用鸣谢曲
            if getattr(self, "ending_page", 0) >= len(self.ENDING_PAGES) - 1:
                self.audio.play_music("credits")
            else:
                self.audio.play_music("ending")
            return
        # 最终 Boss 击破仪式：播 U.N.OWEN 这首最知名的东方曲
        if getattr(self, "boss_ceremony_timer", 0.0) > 0.0:
            self.audio.play_music("ceremony")
            return
        director = getattr(self, "director", None)
        if director is None:
            return
        # Boss 战：按 Boss 切换专属曲目
        if director.state == FIGHT and self.boss is not None:
            key = self.boss.spec.key
            boss_music = {
                "rumia": "boss_rumia",
                "cirno": "boss_cirno",
                "remilia": "boss_remilia",
            }.get(key)
            if boss_music:
                self.audio.play_music(boss_music)
                return
        # 非战斗：按关卡切换关卡曲
        stage_music = {1: "stage1", 2: "stage2", 3: "stage3"}.get(
            director.stage_number, "stage1"
        )
        self.audio.play_music(stage_music)

    def update(self, dt: float) -> None:
        self._update_music()
        self._advance_credits_roll(dt)
        if self.scene != self.SCENE_PLAYING:
            return
        if (self.paused or getattr(self, "cheat_prompt_active", False)
                or getattr(self, "quit_confirm_active", False)):
            self.shoot_requested = False
            return
        if self.victory or self.game_over:
            # 结算画面仍需让特效播完、红屏闪烁淡出
            self.shoot_requested = False
            self._advance_effects(dt)
            self.hit_flash = max(0.0, self.hit_flash - dt)
            self._decay_screen_shake(dt)
            return

        self._advance_effects(dt)
        self.boss_flash = max(0.0, self.boss_flash - dt)
        self.bomb_timer = max(0.0, self.bomb_timer - dt)
        self._recharge_bombs(dt)

        # 最终 Boss 击破仪式：白闪消退、震屏衰减、慢动作播放粒子，结束后才推进剧情
        if getattr(self, "boss_ceremony_timer", 0.0) > 0.0:
            ceremony_dt = dt * 0.35          # 慢动作：粒子以 35% 速度推进
            for effect in self.effects:
                effect.update(ceremony_dt)
            self.boss_ceremony_timer = max(0.0, self.boss_ceremony_timer - dt)
            # 仪式用更慢的衰减，让击破的余震持续得久一些
            self._decay_screen_shake(dt, rate=40.0)
            self.shoot_requested = False
            if self.boss_ceremony_timer <= 0.0:
                self.screen_shake = 0.0
                director = getattr(self, "director", None)
                if director is not None:
                    director.notify_boss_defeated()
            return

        self._decay_screen_shake(dt)

        # 关卡推进：过场 / 对话 / 波次 / 战斗 / 结算全由 director 编排
        self.fairies.extend(
            self.director.update(dt, len(self.fairies))
        )
        spec = self.director.take_boss()
        if spec is not None:
            self._spawn_boss(spec)
        if self.director.cleared_stage > self.awarded_clear:
            # 每通过一关发一次通关奖励（原作「ステージクリア」结算）
            self.awarded_clear = self.director.cleared_stage
            self.score += config.STAGE_CLEAR_BONUS
        if self.director.completed:
            # 单关结束：解锁下一关并保存进度；最终关才进入结局
            cleared = self.director.stage_number
            if cleared >= self.unlocked_stage and cleared < config.STAGE_COUNT:
                self.unlocked_stage = cleared + 1
            if cleared >= config.STAGE_COUNT:
                self.all_cleared = True
            _save_progress(self.unlocked_stage, self.all_cleared)
            self._register_hiscore()
            if cleared >= config.STAGE_COUNT:
                self.victory = True
            else:
                self.stage_select_index = min(
                    self.stage_select_index, self.unlocked_stage - 1
                )
                self.scene = self.SCENE_STAGE_SELECT
            return
        if self.director.state in (BANNER, TALK):
            # 过场与对话期间冻结弹幕场，只让已有效果播完
            self.shoot_requested = False
            return

        self.invulnerable_timer = max(0.0, self.invulnerable_timer - dt)
        self.graze_fx_cooldown = max(0.0, self.graze_fx_cooldown - dt)
        self._update_player_skill(dt)
        self._update_power_growth(dt)
        self.debug_stats = self._empty_debug_stats()
        self.focus, self.shooting = self._read_player_input()
        self.player.update(dt)

        # 限制在窗口内
        self.player.pos.x = max(
            config.PLAYFIELD_LEFT + self.player.radius,
            min(config.PLAYFIELD_RIGHT - self.player.radius, self.player.pos.x),
        )
        self.player.pos.y = max(
            config.PLAYFIELD_TOP + self.player.radius,
            min(config.PLAYFIELD_BOTTOM - self.player.radius, self.player.pos.y),
        )
        self.animation_timer += dt
        self._update_fairies(dt)
        self._update_items(dt)

        if self.boss is not None and self.boss.alive:
            self.boss.update(dt)
        self._spawn_player_shots(dt)
        self.shoot_requested = False
        for shot in self.player_shots:
            shot.update(dt)
        self._check_fairy_collisions()
        self._check_boss_collisions()
        if self.victory:
            return

        self._update_boss_attacks(dt)
        if self.spell_announce_timer > 0.0:
            self.spell_announce_timer = max(0.0, self.spell_announce_timer - dt)
        if self.boss_skill_announce_timer > 0.0:
            self.boss_skill_announce_timer = max(
                0.0, self.boss_skill_announce_timer - dt
            )
        # 时间凝滞：技能生效期间，敌弹按缩放后的 dt 推进（玩家弹不受影响）
        slow = 1.0
        if self.bullet_slow_timer > 0.0:
            slow = config.PLAYER_SKILL_SLOW_FACTOR
            self.bullet_slow_timer = max(0.0, self.bullet_slow_timer - dt)
        for b in self.bullets:
            b.update(dt * slow)
        self.bullets = [b for b in self.bullets if b.alive]
        for beam in getattr(self, "boss_beams", ()):
            beam.update(dt)
        self.boss_beams = [beam for beam in self.boss_beams if beam.alive]

        self._check_collisions()

        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

        if self.skill_flash > 0.0:
            self.skill_flash = max(0.0, self.skill_flash - dt)

        if self.power_up_timer > 0.0:
            self.power_up_timer = max(0.0, self.power_up_timer - dt)

    # ------------------------------------------------------------------ #
    # 渲染
    # ------------------------------------------------------------------ #
    def _render(self) -> None:
        if self.scene == self.SCENE_TITLE:
            self._draw_title_screen()
            return
        if self.scene == self.SCENE_CONTROLS:
            self._draw_manual_screen()
            return
        if self.scene == self.SCENE_STAGE_SELECT:
            self._draw_stage_select()
            return
        if self.scene == self.SCENE_AFTERWORD:
            self._draw_afterword_view()
            return
        if self.scene == self.SCENE_CG_GALLERY:
            self._draw_cg_gallery()
            return

        field_origin = (config.PLAYFIELD_LEFT, config.PLAYFIELD_TOP)
        self.screen.blit(self.art.scene_background, (0, 0))
        backgrounds = self.art.stage_backgrounds
        background_index = min(
            self.director.background_index, len(backgrounds) - 1
        )
        self.screen.blit(backgrounds[background_index], field_origin)
        self.screen.blit(self.playfield_shade, field_origin)
        self.screen.blit(self.field_vignette, field_origin)

        for fairy in self.fairies:
            fairy.draw(
                self.screen,
                self.art.enemy_frames.get(fairy.frames_key)
                or self.art.fairy_frames,
                flash=fairy.hit_flash / config.BOSS_FLASH_DURATION,
            )

        for item in self.items:
            item.draw(self.screen, self.art.item_halo)

        boss = self.boss
        if boss is not None and boss.alive:
            if self.boss_skill_timer > 0.0:
                self._draw_charge_aura(boss, boss.spec.special)
            boss_sprite = self._boss_sprite(boss)
            if self.boss_flash > 0.0:
                boss_sprite = _flash_sprite(
                    boss_sprite, self.boss_flash / config.BOSS_FLASH_DURATION
                )
            boss.draw(self.screen, boss_sprite)

        shot_sprite = self._player_shot_sprite()
        shot_trail = self._player_shot_trail()
        for shot in self.player_shots:
            if shot.alive:
                shot.draw(self.screen, shot_sprite, shot_trail)
        blinking = (
            self.invulnerable_timer > 0.0
            and int(self.invulnerable_timer * 12) % 2 == 0
        )
        if not blinking:
            # 按本帧横向移动方向挑帧组，静止时回到直立组
            if self.player.vel.x < -1.0:
                frames = self.art.player_frames_left
            elif self.player.vel.x > 1.0:
                frames = self.art.player_frames_right
            else:
                frames = self.art.player_frames
            self.player.draw(
                self.screen,
                focus=self.focus,
                sprite=frames[int(self.animation_timer * 8) % len(frames)],
            )
        if self.skill_state == "charge":
            self._draw_charge_aura(self.player, None)

        for b in self.bullets:
            b.draw(self.screen)          # 子弹自持贴图，无需外部查表
        for beam in self.boss_beams:
            beam.draw(self.screen)
        for effect in self.effects:
            effect.draw(self.screen)

        if self.hit_flash > 0:
            self.hit_overlay.set_alpha(round(90 * self.hit_flash / 0.25))
            self.screen.blit(self.hit_overlay, field_origin)

        if self.skill_flash > 0.0:
            self.skill_overlay.set_alpha(
                round(150 * self.skill_flash / config.BOSS_SKILL_FLASH)
            )
            self.screen.blit(self.skill_overlay, field_origin)

        if self.bullet_slow_timer > 0.0:
            fade = min(1.0, self.bullet_slow_timer / 0.6)
            self.slow_overlay.set_alpha(round(255 * fade))
            self.screen.blit(self.slow_overlay, field_origin)

        if self.debug_overlay:
            self._draw_debug_overlay()

        self._draw_phase_hud()
        self._draw_spell_announcement()
        self._draw_boss_skill_announcement()
        self._draw_power_up_banner()
        self._draw_hud()

        # 震屏：把画好的场地与 HUD 整体偏移重绘，其上的对话框 / 大字卡保持稳定
        self._apply_screen_shake()

        director = self.director
        if self.paused:
            self._draw_pause_card()
        elif self.game_over:
            self._draw_ending(self.art.ending_defeat, victory=False)
        elif self.victory:
            ending_background = self._ending_background_for_page(self.ending_page)
            self._draw_ending(ending_background, victory=True)
        elif director.state == BANNER:
            self._draw_banner_card()
        elif director.waiting_dialogue and director.dialogue is not None:
            director.dialogue.draw(
                self.screen, self.art, self.font, self.font_big
            )

        # 最终 Boss 击破仪式：白闪 + 「異変終結」大字卡
        if self.boss_ceremony_timer > 0.0:
            self._draw_boss_ceremony()

        # 作弊密码输入框始终置顶
        if self.cheat_prompt_active:
            self._draw_cheat_prompt()

        # 关卡内按 Esc 弹出的「返回标题」确认框
        if getattr(self, "quit_confirm_active", False):
            self._draw_quit_confirm(
                "返回標題？", "確定要放棄本局並回到標題嗎？"
            )

    def _boss_sprite(self, boss: Boss) -> pygame.Surface:
        """取当前 Boss 的立绘：按角色键取一组表情，再按符卡序号选一张。"""
        group = self.art.hud_portraits.get(boss.spec.key)
        if not group:
            group = self.art.boss_faces
        return group[min(boss.phase, len(group)) - 1]

    def _draw_ornate_panel(self, rect: pygame.Rect, alpha: int = 236) -> None:
        return render._draw_ornate_panel(self, rect, alpha)

    def _apply_screen_shake(self) -> None:
        return render._apply_screen_shake(self)

    def _draw_boss_ceremony(self) -> None:
        return render._draw_boss_ceremony(self)

    def _draw_cheat_prompt(self) -> None:
        return render._draw_cheat_prompt(self)

    def _draw_banner_card(self) -> None:
        return render._draw_banner_card(self)

    def _draw_ending(self, background: pygame.Surface, victory: bool) -> None:
        return render._draw_ending(self, background, victory)

    def _draw_victory_text_page(self, panel: pygame.Rect) -> None:
        return render._draw_victory_text_page(self, panel)

    # 謝辞滚动名单的行高：按行的种类决定疏密
    CREDITS_BLOCK_HEIGHT = {
        "big": 78, "small": 36, "gap": 34, "row": 52, "thanks": 60,
    }

    def _credits_roll_blocks(self) -> list[tuple[str, str]]:
        return render._credits_roll_blocks(self)

    def _draw_credits_roll(self) -> None:
        return render._draw_credits_roll(self)

    def _draw_pause_card(self) -> None:
        return render._draw_pause_card(self)

    def _draw_stage_select(self) -> None:
        return render._draw_stage_select(self)

    def _draw_afterword_view(self) -> None:
        return render._draw_afterword_view(self)

    def _background_surface(self, key: str) -> pygame.Surface:
        return render._background_surface(self, key)

    def _draw_cg_gallery(self) -> None:
        return render._draw_cg_gallery(self)

    def _draw_gallery_tabs(self, panel: pygame.Rect) -> None:
        return render._draw_gallery_tabs(self, panel)

    def _draw_background_gallery(self, panel: pygame.Rect) -> None:
        return render._draw_background_gallery(self, panel)

    def _draw_character_record(self, panel: pygame.Rect) -> None:
        return render._draw_character_record(self, panel)

    def _draw_music_room(self, panel: pygame.Rect) -> None:
        return render._draw_music_room(self, panel)

    def _wrap_text(self, text: str, font: pygame.font.Font,
                   max_width: int) -> list[str]:
        return render._wrap_text(self, text, font, max_width)


    # 每页日后谈对应的背景与立绘：营造原作 CG 感，而非纯文本。
    AFTERWORD_PAGE_VISUALS = (
        ("scene", "remilia", 0),   # 第1页：红魔馆内，蕾米莉亚
        ("afterword", "cirno", 0), # 第2页：雾之湖畔，琪露诺
        ("victory", "sakuya", 0),  # 第3页：红魔馆日常，咲夜
    )

    def _ending_background_for_page(self, page: int) -> pygame.Surface:
        return render._ending_background_for_page(self, page)

    def _draw_title_screen(self) -> None:
        return render._draw_title_screen(self)

    def _draw_quit_confirm(self, title: str = "退出游戏？",
                           body: str = "確定要離開東方紅霧録嗎？") -> None:
        return render._draw_quit_confirm(self, title, body)

    def _draw_manual_screen(self) -> None:
        return render._draw_manual_screen(self)

    def _draw_story_page(self, left: int, top: int) -> None:
        return render._draw_story_page(self, left, top)

    def _draw_terms_page(self, left: int, right: int, top: int) -> None:
        return render._draw_terms_page(self, left, right, top)

    def _draw_controls_page(self, left: int, right: int, top: int) -> None:
        return render._draw_controls_page(self, left, right, top)

    def _draw_text_centered(
            self, text: str, y: int, color, font: pygame.font.Font) -> None:
        return render._draw_text_centered(self, text, y, color, font)

    def _draw_debug_overlay(self) -> None:
        return render._draw_debug_overlay(self)







    def _draw_center_text(
            self, text: str, color, font: pygame.font.Font | None = None,
            y: float | None = None, center_x: int | None = None) -> None:
        return render._draw_center_text(self, text, color, font, y, center_x)

    def _draw_phase_hud(self) -> None:
        hud.draw_phase_hud(self)

    def _draw_power_up_banner(self) -> None:
        hud.draw_power_up_banner(self)

    def _draw_spell_announcement(self) -> None:
        hud.draw_spell_announcement(self)

    def _draw_charge_aura(self, entity, special) -> None:
        hud.draw_charge_aura(self, entity, special)

    def _draw_boss_skill_announcement(self) -> None:
        hud.draw_boss_skill_announcement(self)

    def _draw_hud(self) -> None:
        hud.draw_hud(self)

    # ------------------------------------------------------------------ #
    # 主循环
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(config.FPS) / 1000.0, config.MAX_DT)
            self._handle_events()
            self.update(dt)
            self._render()
            pygame.display.flip()
        pygame.quit()
