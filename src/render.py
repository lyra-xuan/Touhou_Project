"""Screen and menu rendering functions operating on a Game instance."""
from __future__ import annotations

import math
import random

import pygame

from . import config


def _draw_ornate_panel(game, rect: pygame.Rect, alpha: int = 236) -> None:
    """绘制半透明双线描金卡片，底图始终保留原作素材。"""
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((10, 5, 12, alpha))
    game.screen.blit(panel, rect.topleft)
    pygame.draw.rect(game.screen, config.GOLD, rect, 2)
    pygame.draw.rect(game.screen, (120, 68, 54), rect.inflate(-14, -14), 1)


def _apply_screen_shake(game) -> None:
    """将整屏内容随机偏移，模拟击破最终 Boss 时的震屏。"""
    magnitude = game.screen_shake
    if magnitude <= 0.0:
        return
    dx = random.uniform(-magnitude, magnitude)
    dy = random.uniform(-magnitude, magnitude)
    snapshot = game.screen.copy()
    game.screen.fill(config.BLACK)
    game.screen.blit(snapshot, (round(dx), round(dy)))


def _draw_boss_ceremony(game) -> None:
    """最终 Boss 击破仪式：白闪 + 赤红闪 + 「異変終結」大字卡 + 全符卡破却。"""
    field = pygame.Rect(
        config.PLAYFIELD_LEFT, config.PLAYFIELD_TOP,
        config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT,
    )
    total = 3.6
    t = game.boss_ceremony_timer
    elapsed = total - t

    # 第一段：白闪（前 0.5 秒全白，之后渐隐）
    flash_t = max(0.0, t - (total - 0.5))
    flash_alpha = min(255, int(255 * flash_t / 0.5))
    if flash_alpha > 0:
        white = pygame.Surface(field.size, pygame.SRCALPHA)
        white.fill((255, 250, 240, flash_alpha))
        game.screen.blit(white, field.topleft)

    # 第二段：赤红闪（仪式中段，约 1.6s ~ 2.2s 处浮现）
    red_flash = 0.0
    if 1.6 <= elapsed <= 2.2:
        if elapsed < 1.9:
            red_flash = (elapsed - 1.6) / 0.3
        else:
            red_flash = (2.2 - elapsed) / 0.3
    red_alpha = int(180 * max(0.0, min(1.0, red_flash)))
    if red_alpha > 0:
        red = pygame.Surface(field.size, pygame.SRCALPHA)
        red.fill((200, 30, 40, red_alpha))
        game.screen.blit(red, field.topleft)

    # 文字卡：仪式中段浮现，后段淡出
    if 0.4 < t < total - 0.3:
        fade_in = min(1.0, (total - 0.3 - t) / 0.5)
        fade_out = min(1.0, t / 0.6)
        alpha = int(255 * min(fade_in, fade_out))
        cx = config.PLAYFIELD_LEFT + config.PLAYFIELD_WIDTH // 2
        cy = config.PLAYFIELD_TOP + config.PLAYFIELD_HEIGHT // 2

        title = game.font_big.render("異変終結", True, config.PALE_GOLD)
        title.set_alpha(alpha)
        shadow = game.font_big.render("異変終結", True, config.BLACK)
        shadow.set_alpha(alpha)
        game.screen.blit(shadow, shadow.get_rect(center=(cx + 3, cy + 3)))
        game.screen.blit(title, title.get_rect(center=(cx, cy)))

        sub = game.font.render(
            "INCIDENT RESOLVED  /  紅霧散去", True, config.WHITE,
        )
        sub.set_alpha(alpha)
        game.screen.blit(sub, sub.get_rect(center=(cx, cy + 56)))

        # 全符卡破却：在赤红闪之后浮现
        if elapsed > 2.0:
            broken_alpha = int(255 * min(1.0, (elapsed - 2.0) / 0.4))
            broken = game.font.render(
                "全符卡破却  /  ALL SPELL CARDS BROKEN", True, config.GOLD,
            )
            broken.set_alpha(min(alpha, broken_alpha))
            game.screen.blit(broken, broken.get_rect(center=(cx, cy + 100)))


def _draw_cheat_prompt(game) -> None:
    """作弊密码输入框：居中卡片，显示已输入的数字（用●遮掩）。"""
    panel = pygame.Rect(config.SCREEN_W // 2 - 260, config.SCREEN_H // 2 - 90,
                        520, 180)
    game._draw_ornate_panel(panel)
    cx = panel.centerx
    game.screen.blit(
        game.font.render("異變調查員認證  /  CHEAT CODE", True, config.MUTED),
        game.font.render("異變調查員認證  /  CHEAT CODE", True, config.MUTED
                         ).get_rect(center=(cx, panel.top + 40)),
    )
    # 密码用 ● 遮掩，已输入位数高亮
    pwd_len = len(game.CHEAT_PASSWORD)
    masked = " ".join("●" if i < len(game.cheat_input) else "○"
                      for i in range(pwd_len))
    game.screen.blit(
        game.font_big.render(masked, True, config.PALE_GOLD),
        game.font_big.render(masked, True, config.PALE_GOLD
                             ).get_rect(center=(cx, panel.top + 100)),
    )
    game.screen.blit(
        game.font.render("输入 6 位密码  ·  Esc 取消", True, config.WHITE),
        game.font.render("输入 6 位密码  ·  Esc 取消", True, config.WHITE
                         ).get_rect(center=(cx, panel.bottom - 36)),
    )


def _draw_banner_card(game) -> None:
    """关卡标题过场：以横幅卡片呈现本关的舞台、中 Boss 与首领。"""
    banner = game.director.banner
    if banner is None:
        return
    game.screen.blit(game.entry_shade, (0, 0))

    panel = pygame.Rect(158, 244, 964, 472)
    game._draw_ornate_panel(panel)
    left = panel.left + 48
    game.screen.blit(
        game.font.render(
            f"異変調査記録  /  INCIDENT FILE {banner.stage_index:02d}",
            True, config.MUTED,
        ),
        (left, panel.top + 38),
    )
    game.screen.blit(
        game.font_big.render(banner.title, True, config.PALE_GOLD),
        (left, panel.top + 88),
    )
    game.screen.blit(
        game.font.render(banner.subtitle, True, config.WHITE),
        (left, panel.top + 148),
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 198), (panel.right - 48, panel.top + 198), 1,
    )
    script = game.director.script
    rows: list[tuple[str, str]] = []
    if script is not None:
        rows.append(("中首領  /  MIDBOSS",
                     script.midboss.title if script.midboss else "（無）"))
        rows.append(("首領  /  BOSS", script.boss.title))
        rows.append(("符卡  /  SPELL CARD",
                     f"{len(script.boss.spells)} 張"))
    for index, (label, value) in enumerate(rows):
        y = panel.top + 222 + index * 44
        game.screen.blit(
            game.font.render(label, True, config.PALE_GOLD), (left, y)
        )
        game.screen.blit(
            game.font.render(value, True, config.WHITE),
            (left + 260, y),
        )

    if script is not None:
        portrait_group = game.art.hud_portraits.get(script.boss.key) or ()
        if portrait_group:
            portrait = portrait_group[0]
            game.screen.blit(
                portrait,
                portrait.get_rect(
                    midright=(panel.right - 54, panel.centery + 8)
                ),
            )

    game.screen.blit(
        game.font.render("避開彈幕，破除符卡。", True, config.PALE_GOLD),
        (left, panel.bottom - 62),
    )


def _draw_ending(game, background: pygame.Surface, victory: bool) -> None:
    """結算回顾：原作插图、关卡进度、战绩与再战指引。"""
    if victory and game.ending_page >= len(game.ENDING_PAGES) - 1:
        # 謝辞页是滚动制作名单，自带原作插画背景，不再套金边卡片
        game._draw_credits_roll()
        return

    text_page = victory and game.ending_page > 0
    game.screen.blit(background, (0, 0))
    # 后记文字页只轻压暗，让原作插图留在画面里
    game.screen.blit(
        game.ending_light_shade if text_page else game.ending_shade, (0, 0)
    )
    panel = pygame.Rect(120, 128, 1040, 704)
    game._draw_ornate_panel(panel, alpha=136 if text_page else 236)
    left = panel.left + 58
    if text_page:
        game._draw_victory_text_page(panel)
        return

    heading = "異変解決" if victory else "霊力尽きる"
    english = "INCIDENT RESOLVED" if victory else "INCIDENT UNRESOLVED"
    game.screen.blit(
        game.font_big.render(heading, True, config.PALE_GOLD),
        (left, panel.top + 48),
    )
    game.screen.blit(
        game.font.render(english, True, config.MUTED),
        (left, panel.top + 112),
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 158), (panel.right - 58, panel.top + 158), 1,
    )
    total_stages = max(1, len(game.director.stages))
    stage_no = min(max(game.director.stage_number, 1), total_stages)
    game.screen.blit(
        game.font.render("紅霧異変  /  紅魔館異聞", True, config.PALE_GOLD),
        (left, panel.top + 184),
    )
    if victory:
        progress = f"全 {total_stages} 關  /  ALL STAGES CLEARED"
    else:
        progress = f"到達  /  STAGE {stage_no} / {total_stages}"
        if game.boss is not None:
            progress += f"  「{game.boss.spell.name}」"
    game.screen.blit(
        game.font.render(progress, True, config.WHITE),
        (left, panel.top + 232),
    )
    game.screen.blit(
        game.font.render(
            f"得分  {game.score:08d}      最高分  {game.hiscore:08d}",
            True, config.WHITE,
        ),
        (left, panel.top + 302),
    )
    game.screen.blit(
        game.font.render(
            f"擦彈 {game.graze_total}    命中 {game.hit_total}    "
            f"道具 {game.item_total}",
            True, config.MUTED,
        ),
        (left, panel.top + 350),
    )
    game.screen.blit(
        game.font.render(
            f"符卡取得  {game.spells_captured}    失敗  {game.spells_failed}",
            True, config.PALE_GOLD,
        ),
        (left, panel.top + 398),
    )

    result_rect = game.art.result_screen.get_rect(
        midright=(panel.right - 58, panel.top + 380)
    )
    pygame.draw.rect(
        game.screen, config.GOLD, result_rect.inflate(4, 4), 1
    )
    game.screen.blit(
        game.art.result_screen, result_rect,
    )
    game.screen.blit(
        game.font.render("紅魔郷 SCORE / RESULT", True, config.PALE_GOLD),
        (result_rect.left, result_rect.bottom + 16),
    )
    pygame.draw.line(
        game.screen, (120, 68, 54),
        (left, panel.bottom - 116), (panel.right - 58, panel.bottom - 116), 1,
    )
    game.screen.blit(
        game.font.render(
            "Enter / → 閱讀後記  ·  R 再戰  ·  Esc 返回標題",
            True, config.WHITE,
        ),
        (left, panel.bottom - 80),
    )


def _draw_victory_text_page(game, panel: pygame.Rect) -> None:
    """原作式後記页：半透明金边卡片上排字，襯以對應的結局原圖。"""
    page = game.ending_page
    left = panel.left + 58
    right = panel.right - 58
    afterword_count = len(game.VICTORY_AFTERWORD_PAGES)

    game.screen.blit(
        game.font_big.render("後記", True, config.PALE_GOLD),
        (left, panel.top + 42),
    )
    game.screen.blit(
        game.font.render(
            f"AFTERWORD  /  異変のあと  {page} / {afterword_count}",
            True, config.MUTED,
        ),
        (left, panel.top + 108),
    )
    page_label = game.font.render(
        f"{page + 1} / {len(game.ENDING_PAGES)}", True, config.PALE_GOLD
    )
    game.screen.blit(page_label, page_label.get_rect(topright=(right, panel.top + 68)))
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 158), (right, panel.top + 158), 1,
    )

    # 每页日后谈配一张角色立绘，营造原作 CG 感（右侧底部对齐）。
    afterword_index = page - 1
    if 0 <= afterword_index < len(game.AFTERWORD_PAGE_VISUALS):
        _, portrait_key, portrait_idx = game.AFTERWORD_PAGE_VISUALS[
            afterword_index
        ]
        portraits = game.art.portraits.get(portrait_key)
        if portraits and 0 <= portrait_idx < len(portraits):
            portrait = portraits[portrait_idx]
            px = panel.right - 40 - portrait.get_width()
            py = panel.bottom - 120 - portrait.get_height()
            # 立绘下方加一层柔光，让角色从卡片中浮起。
            glow = pygame.Surface(
                (portrait.get_width() + 40, portrait.get_height() + 40),
                pygame.SRCALPHA,
            )
            pygame.draw.ellipse(
                glow, (120, 68, 54, 55), glow.get_rect().inflate(-6, -6)
            )
            game.screen.blit(glow, (px - 20, py - 20))
            game.screen.blit(portrait, (px, py))

    y = panel.top + 194
    for line in game.VICTORY_AFTERWORD_PAGES[page - 1]:
        if line:
            game.screen.blit(
                game.font.render(line, True, config.WHITE), (left, y)
            )
            y += 38
        else:
            y += 22

    if page == afterword_count:
        hint = "← 上一頁  ·  → / Enter 謝辞  ·  R 再戰  ·  Esc 標題"
    else:
        hint = "← 上一頁  ·  → / Enter 下一頁  ·  R 再戰  ·  Esc 標題"

    divider_y = panel.bottom - 116
    pygame.draw.line(
        game.screen, (120, 68, 54),
        (left, divider_y), (right, divider_y), 1,
    )
    game.screen.blit(
        game.font.render(hint, True, config.WHITE),
        (left, panel.bottom - 80),
    )


def _credits_roll_blocks(game) -> list[tuple[str, str]]:
    """謝辞名单内容：页首 → 制作名单 → 致谢 → 尾声，自上而下排列。"""
    blocks: list[tuple[str, str]] = [
        ("big", "謝辞"),
        ("small", "STAFF ROLL  /  ACKNOWLEDGMENTS"),
        ("gap", ""),
    ]
    blocks += [("row", f"{label}　　{value}")
               for label, value in game.VICTORY_CREDITS]
    blocks.append(("gap", ""))
    blocks += [("thanks", line) for line in game.VICTORY_THANKS]
    blocks += [
        ("gap", ""),
        ("small", "東方紅霧録  /  SCARLET MIST RECORD"),
        ("gap", ""),
        ("thanks", "おわり"),
    ]
    return blocks


def _draw_credits_roll(game) -> None:
    """謝辞页：原作结局插画轮播 + 自下而上滚动的制作名单。

    滚动耗时固定为 :attr:`CREDITS_SCROLL_SECONDS`；滚完后停在末页继续
    放着谢辞曲，等玩家按 Enter 才回标题。
    """
    images = game.credits_roll_images
    elapsed = min(getattr(game, "credits_time", 0.0),
                  game.CREDITS_SCROLL_SECONDS)
    if images:
        span = game.CREDITS_SCROLL_SECONDS / len(images)
        position = elapsed / span
        index = int(position) % len(images)
        frac = position - int(position)
        if frac < 0.45 and index != 0:
            # 换图时用前一张垫底、新图淡入，避免硬切
            game.screen.blit(images[index - 1], (0, 0))
            images[index].set_alpha(int(255 * (frac / 0.45)))
            game.screen.blit(images[index], (0, 0))
            images[index].set_alpha(255)
        else:
            game.screen.blit(images[index], (0, 0))
    veil = pygame.Surface((config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA)
    veil.fill((6, 3, 8, 172))
    game.screen.blit(veil, (0, 0))

    blocks = game._credits_roll_blocks()
    heights = [game.CREDITS_BLOCK_HEIGHT[kind] for kind, _ in blocks]
    total = sum(heights)
    start_y = config.SCREEN_H + 40
    end_y = config.SCREEN_H - 150 - total
    progress = min(1.0, elapsed / game.CREDITS_SCROLL_SECONDS)
    y = start_y + (end_y - start_y) * progress

    center_x = config.SCREEN_W // 2
    for (kind, text), height in zip(blocks, heights):
        if kind != "gap" and -60 <= y <= config.SCREEN_H + 60:
            game._draw_center_text(
                text, config.WHITE if kind == "thanks" else config.PALE_GOLD,
                font=game.font_big if kind == "big" else game.font,
                y=y + height // 2, center_x=center_x,
            )
        y += height

    if progress >= 1.0:
        game._draw_center_text(
            "Enter 返回標題", config.PALE_GOLD, font=game.font,
            y=config.SCREEN_H - 62, center_x=center_x,
        )


def _draw_pause_card(game) -> None:
    """暂停过场：保留战场和 HUD，展示正在展开的符卡。"""
    panel = pygame.Rect(198, 304, 884, 352)
    game._draw_ornate_panel(panel)
    center_x = panel.centerx
    game._draw_center_text(
        "弾幕一時停止", config.PALE_GOLD,
        y=panel.top + 62, center_x=center_x,
    )
    game._draw_center_text(
        "PAUSED  /  SPELL CARD", config.MUTED,
        font=game.font, y=panel.top + 124, center_x=center_x,
    )
    if game.boss is not None:
        spell_text = (
            f"{game.boss.spec.title}  "
            f"第 {game.boss.phase} 符卡 「{game.boss.spell.name}」"
            f"  {game.boss.phase} / {game.boss.spell_count}"
        )
    else:
        spell_text = "雜兵波次進行中"
    game._draw_center_text(
        spell_text, config.WHITE, font=game.font,
        y=panel.top + 192, center_x=center_x,
    )
    game._draw_center_text(
        "F1 继续弹幕  ·  Esc 退出异变调查",
        config.PALE_GOLD, font=game.font,
        y=panel.top + 258, center_x=center_x,
    )


def _draw_stage_select(game) -> None:
    """关卡选择界面：列出三关，锁定的关显示锁形，当前选中高亮。"""
    game.screen.blit(game.stage_select_background, (0, 0))
    game.screen.blit(game.stage_select_shade, (0, 0))

    panel = pygame.Rect(220, 120, config.SCREEN_W - 440, config.SCREEN_H - 240)
    game._draw_ornate_panel(panel, alpha=200)
    left = panel.left + 48
    right = panel.right - 48

    game.screen.blit(
        game.font_big.render("選擇關卡", True, config.PALE_GOLD),
        (left, panel.top + 36),
    )
    game.screen.blit(
        game.font.render("SELECT STAGE  /  紅霧異変", True, config.MUTED),
        (left, panel.top + 100),
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 148), (right, panel.top + 148), 1,
    )

    row_h = 132
    start_y = panel.top + 184
    for index in range(config.STAGE_COUNT):
        unlocked = index < game.unlocked_stage
        selected = index == game.stage_select_index
        y = start_y + index * row_h
        row = pygame.Rect(left, y, right - left, row_h - 16)

        if selected:
            sel = pygame.Surface(row.size, pygame.SRCALPHA)
            sel.fill((92, 20, 34, 180))
            game.screen.blit(sel, row.topleft)
        pygame.draw.rect(game.screen, config.GOLD, row, 1 if selected else 0)

        # 关卡编号
        game.screen.blit(
            game.font_big.render(
                f"{index + 1:02d}",
                True, config.PALE_GOLD if unlocked else config.GRAY,
            ),
            (row.left + 24, row.top + 18),
        )
        # 标题与副标题
        title_color = config.WHITE if unlocked else config.GRAY
        game.screen.blit(
            game.font.render(
                game.STAGE_TITLES[index], True, title_color,
            ),
            (row.left + 110, row.top + 22),
        )
        game.screen.blit(
            game.font.render(
                game.STAGE_SUBTITLES[index], True, config.MUTED,
            ),
            (row.left + 110, row.top + 58),
        )
        # Boss 名
        boss_color = config.PALE_GOLD if unlocked else config.GRAY
        game.screen.blit(
            game.font.render(
                f"首領  /  {game.STAGE_BOSS_NAMES[index]}",
                True, boss_color,
            ),
            (row.left + 110, row.top + 90),
        )
        # 锁定标记
        if not unlocked:
            lock = game.font.render("🔒 LOCKED", True, config.GRAY)
            game.screen.blit(
                lock, lock.get_rect(midright=(row.right - 24, row.centery)),
            )
        elif selected:
            arrow = game.font.render("▶ ENTER", True, config.PALE_GOLD)
            game.screen.blit(
                arrow, arrow.get_rect(midright=(row.right - 24, row.centery)),
            )

    pygame.draw.line(
        game.screen, (120, 68, 54),
        (left, panel.bottom - 96), (right, panel.bottom - 96), 1,
    )
    hint = "↑ ↓ 選擇關卡    Enter 開始    Esc 返回標題"
    game.screen.blit(
        game.font.render(hint, True, config.WHITE),
        (left, panel.bottom - 64),
    )


def _draw_afterword_view(game) -> None:
    """从菜单进入的日后谈翻阅：复用结局页面的渲染逻辑。"""
    ending_background = game._ending_background_for_page(game.ending_page)
    game._draw_ending(ending_background, victory=True)


def _background_surface(game, key: str) -> pygame.Surface:
    """把背景図鑑的取图键映射到已加载的整屏画面。"""
    stages = game.art.stage_backgrounds
    if key.startswith("stage") and key[5:].isdigit():
        index = min(int(key[5:]) - 1, len(stages) - 1)
        return stages[index]
    if key.startswith("roll") and key[4:].isdigit():
        index = min(int(key[4:]) - 1, len(game.credits_roll_images) - 1)
        return game.credits_roll_images[index]
    fixed = {
        "scene": game.art.scene_background,
        "victory": game.art.ending_victory,
        "defeat": game.art.ending_defeat,
        "afterword": game.art.ending_afterword,
        "result": game.art.result_screen,
        "title": game.title_background,
        "music": game.music_room_background,
    }
    return fixed.get(key, game.art.scene_background)


def _draw_cg_gallery(game) -> None:
    """紅霧人物録：人物図鑑 / 背景図鑑 / 音楽室三个页籤共用一个全屏面板。"""
    panel = pygame.Rect(60, 60, config.SCREEN_W - 120, config.SCREEN_H - 120)
    if game.cg_tab == 2:
        game.screen.blit(game.music_room_background, (0, 0))
        game.screen.blit(game.music_room_shade, (0, 0))
        game._draw_music_room(panel)
    elif game.cg_tab == 1:
        game.screen.blit(game.title_background, (0, 0))
        game.screen.blit(game.gallery_shade, (0, 0))
        game._draw_background_gallery(panel)
    else:
        game.screen.blit(game.title_background, (0, 0))
        game.screen.blit(game.gallery_shade, (0, 0))
        game._draw_character_record(panel)
    # 页籤最后绘制，压在内容之上
    game._draw_gallery_tabs(panel)


def _draw_gallery_tabs(game, panel: pygame.Rect) -> None:
    """顶部页籤：人物図鑑 / 背景図鑑 / 音楽室（Tab 轮转）。"""
    labels = game.GALLERY_TABS
    tab_w, tab_h, gap = 170, 40, 10
    total_w = len(labels) * tab_w + (len(labels) - 1) * gap
    start_x = panel.centerx + 40 - total_w // 2
    for index, label in enumerate(labels):
        tab = pygame.Rect(
            start_x + index * (tab_w + gap), panel.top + 30, tab_w, tab_h
        )
        active = index == game.cg_tab
        pygame.draw.rect(
            game.screen, (92, 20, 34) if active else (34, 14, 22), tab
        )
        pygame.draw.rect(game.screen, config.GOLD, tab, 1)
        text = game.font.render(
            label, True, config.PALE_GOLD if active else config.MUTED
        )
        game.screen.blit(text, text.get_rect(center=tab.center))


def _draw_background_gallery(game, panel: pygame.Rect) -> None:
    """背景図鑑：翻阅原作关卡背景、结局插画与标题画面。"""
    game._draw_ornate_panel(panel, alpha=200)
    left = panel.left + 40
    right = panel.right - 40
    name, english, preview = game.background_gallery[game.cg_background_index]

    game.screen.blit(
        game.font_big.render("紅霧背景録", True, config.PALE_GOLD),
        (left, panel.top + 32),
    )
    game.screen.blit(
        game.font.render("BACKGROUND GALLERY  /  原作背景集", True, config.MUTED),
        (left, panel.top + 96),
    )
    counter = game.font.render(
        f"{game.cg_background_index + 1} / {len(game.background_gallery)}",
        True, config.PALE_GOLD,
    )
    game.screen.blit(counter, counter.get_rect(topright=(right, panel.top + 56)))
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 138), (right, panel.top + 138), 1,
    )

    frame = preview.get_rect(center=(panel.centerx, panel.top + 410))
    pygame.draw.rect(game.screen, config.GOLD, frame.inflate(6, 6), 2)
    game.screen.blit(preview, frame)
    game.screen.blit(
        game.font.render(name, True, config.PALE_GOLD),
        (left, frame.bottom + 22),
    )
    game.screen.blit(
        game.font.render(english, True, config.MUTED),
        (left, frame.bottom + 56),
    )

    if game.cg_background_index > 0:
        prev_name = game.background_gallery[game.cg_background_index - 1][0]
        prev = game.font_small.render(f"← {prev_name}", True, config.MUTED)
        game.screen.blit(prev, (left, panel.bottom - 96))
    if game.cg_background_index < len(game.background_gallery) - 1:
        next_name = game.background_gallery[game.cg_background_index + 1][0]
        nxt = game.font_small.render(f"{next_name} →", True, config.MUTED)
        game.screen.blit(nxt, nxt.get_rect(topright=(right, panel.bottom - 96)))

    hint = "← →  切換背景     Tab 切換頁籤     Esc 返回標題"
    game.screen.blit(
        game.font.render(hint, True, config.WHITE),
        (left, panel.bottom - 36),
    )


def _draw_character_record(game, panel: pygame.Rect) -> None:
    """人物図鑑：列表态浏览角色，详情态查看该角色的多张 CG。"""
    game._draw_ornate_panel(panel, alpha=200)
    left = panel.left + 40
    right = panel.right - 40

    entry = game.CG_GALLERY_ENTRIES[game.cg_gallery_index]
    portrait_key, name, en_name, role, lines, short_name = entry
    portrait_group = game.art.portraits.get(portrait_key)
    is_detail = game.cg_detail_active
    cg_count = len(portrait_group) if portrait_group else 1
    cg_index = min(game.cg_detail_cg_index, cg_count - 1) if is_detail else 0

    # 标题区
    if is_detail:
        title_text = name
        sub_text = f"CG 詳情  /  {en_name}"
    else:
        title_text = "紅霧人物録"
        sub_text = "CHARACTER RECORD  /  登場人物図鑑"
    game.screen.blit(
        game.font_big.render(title_text, True, config.PALE_GOLD),
        (left, panel.top + 32),
    )
    game.screen.blit(
        game.font.render(sub_text, True, config.MUTED),
        (left, panel.top + 96),
    )
    if is_detail:
        counter = game.font.render(
            f"CG {cg_index + 1} / {cg_count}", True, config.PALE_GOLD
        )
    else:
        counter = game.font.render(
            f"{game.cg_gallery_index + 1} / {len(game.CG_GALLERY_ENTRIES)}",
            True, config.PALE_GOLD,
        )
    game.screen.blit(
        counter, counter.get_rect(topright=(right, panel.top + 56))
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 138), (right, panel.top + 138), 1,
    )

    # 左侧：大立绘 + 装饰画框
    portrait = portrait_group[cg_index] if portrait_group else None
    if portrait is not None:
        gallery_h = 470
        pw = max(1, round(portrait.get_width() * gallery_h / portrait.get_height()))
        big_portrait = pygame.transform.smoothscale(portrait, (pw, gallery_h))

        frame_pad = 18
        frame_rect = pygame.Rect(0, 0, pw + frame_pad * 2, gallery_h + frame_pad * 2)
        frame_rect.midleft = (left + 8, panel.centery + 10)

        glow = pygame.Surface(
            (frame_rect.width + 60, frame_rect.height + 60), pygame.SRCALPHA
        )
        pygame.draw.ellipse(
            glow, (140, 78, 50, 70), glow.get_rect().inflate(-10, -10)
        )
        game.screen.blit(glow, glow.get_rect(center=frame_rect.center))
        frame_bg = pygame.Surface(frame_rect.size, pygame.SRCALPHA)
        frame_bg.fill((18, 8, 14, 235))
        game.screen.blit(frame_bg, frame_rect.topleft)
        pygame.draw.rect(game.screen, config.GOLD, frame_rect, 2)
        pygame.draw.rect(
            game.screen, (120, 68, 54), frame_rect.inflate(-8, -8), 1
        )
        game.screen.blit(
            big_portrait, big_portrait.get_rect(center=frame_rect.center)
        )

    # 右侧：人物名、英文名、身份、介绍
    text_left = panel.left + 560
    text_right = right
    y = panel.top + 176

    game.screen.blit(game.font_big.render(name, True, config.PALE_GOLD), (text_left, y))
    y += 62
    game.screen.blit(game.font.render(en_name, True, config.MUTED), (text_left, y))
    y += 36
    game.screen.blit(game.font.render(f"【{role}】", True, config.GOLD), (text_left, y))
    y += 56
    pygame.draw.line(
        game.screen, (120, 68, 54),
        (text_left, y), (text_right, y), 1,
    )
    y += 32
    for line in lines:
        surf = game.font.render(line, True, config.WHITE)
        game.screen.blit(surf, (text_left, y))
        y += 40

    # 底部缩略图条
    thumb_h = 86
    thumb_area_top = panel.bottom - 140
    pygame.draw.line(
        game.screen, (120, 68, 54),
        (left, thumb_area_top - 16), (right, thumb_area_top - 16), 1,
    )

    if is_detail:
        # 详情态：显示该角色的所有表情 CG
        thumb_count = cg_count
        thumb_w = 70
        gap = 14
        total_w = thumb_count * thumb_w + (thumb_count - 1) * gap
        start_x = panel.centerx - total_w // 2
        for i in range(thumb_count):
            tx = start_x + i * (thumb_w + gap)
            ty = thumb_area_top
            tframe = pygame.Rect(tx, ty, thumb_w, thumb_h)
            active = i == cg_index
            tbg = pygame.Surface(tframe.size, pygame.SRCALPHA)
            tbg.fill((92, 20, 34, 210) if active else (10, 5, 12, 180))
            game.screen.blit(tbg, tframe.topleft)
            pygame.draw.rect(
                game.screen, config.GOLD if active else (80, 50, 40),
                tframe, 2,
            )
            if portrait_group:
                thumb = pygame.transform.smoothscale(
                    portrait_group[i],
                    (max(1, round(portrait_group[i].get_width() * thumb_h / portrait_group[i].get_height())), thumb_h),
                )
                game.screen.blit(thumb, thumb.get_rect(center=tframe.center))
            label = game.font.render(
                    f"{i + 1}", True, config.PALE_GOLD if active else config.MUTED
                )
            game.screen.blit(
                    label, label.get_rect(midtop=(tframe.centerx, tframe.bottom + 6))
                )
        hint = "← →  切換表情     Esc 返回列表"
    else:
        # 列表态：显示所有角色，缩略图下方用短名避免重叠
        thumb_count = len(game.CG_GALLERY_ENTRIES)
        thumb_w = 72
        gap = 64
        total_w = thumb_count * thumb_w + (thumb_count - 1) * gap
        start_x = panel.centerx - total_w // 2
        for i, (pkey, pname, _, _, _, pshort) in enumerate(game.CG_GALLERY_ENTRIES):
            tx = start_x + i * (thumb_w + gap)
            ty = thumb_area_top
            tframe = pygame.Rect(tx, ty, thumb_w, thumb_h)
            active = i == game.cg_gallery_index
            tbg = pygame.Surface(tframe.size, pygame.SRCALPHA)
            tbg.fill((92, 20, 34, 210) if active else (10, 5, 12, 180))
            game.screen.blit(tbg, tframe.topleft)
            pygame.draw.rect(
                game.screen, config.GOLD if active else (80, 50, 40),
                tframe, 2,
            )
            pgroup = game.art.portraits.get(pkey)
            if pgroup:
                thumb = pygame.transform.smoothscale(
                    pgroup[0],
                    (max(1, round(pgroup[0].get_width() * thumb_h / pgroup[0].get_height())), thumb_h),
                )
                game.screen.blit(thumb, thumb.get_rect(center=tframe.center))
            name_label = game.font.render(
                    pshort, True, config.PALE_GOLD if active else config.MUTED
                )
            game.screen.blit(
                name_label,
                name_label.get_rect(midtop=(tframe.centerx, tframe.bottom + 6)),
            )
        hint = "← →  切換角色     Enter 查看 CG     Tab 切換頁籤     Esc 返回標題"

    game.screen.blit(
        game.font.render(hint, True, config.WHITE),
        (left, panel.bottom - 36),
    )


def _draw_music_room(game, panel: pygame.Rect) -> None:
    """音楽室：左列 TH06 原曲一览，右列所选曲目的 ZUN 评论，Enter 试听。"""
    left = panel.left + 40
    right = panel.right - 40

    def card(rect: pygame.Rect) -> None:
        """音楽室内的半透明卡片：让原作 music.jpg 背景透出来。"""
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill((10, 5, 12, 150))
        game.screen.blit(surface, rect.topleft)
        pygame.draw.rect(game.screen, config.GOLD, rect, 1)

    game.screen.blit(
        game.font_big.render("音楽室", True, config.PALE_GOLD),
        (left, panel.top + 32),
    )
    game.screen.blit(
        game.font.render(
            "MUSIC ROOM  /  東方紅魔郷 全 17 曲", True, config.MUTED
        ),
        (left, panel.top + 96),
    )
    counter = game.font.render(
        f"No.{game.music_room_index + 1:02d} / {len(game.MUSIC_ROOM_TRACKS)}",
        True, config.PALE_GOLD,
    )
    game.screen.blit(counter, counter.get_rect(topright=(right, panel.top + 56)))
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 138), (right, panel.top + 138), 1,
    )

    row_h = 46
    visible = game.MUSIC_ROOM_VISIBLE
    list_rect = pygame.Rect(left, panel.top + 172, 600, visible * row_h + 12)
    card(list_rect)
    for row in range(visible):
        index = game.music_room_scroll + row
        if index >= len(game.MUSIC_ROOM_TRACKS):
            break
        filename, title, _, _ = game.MUSIC_ROOM_TRACKS[index]
        row_rect = pygame.Rect(
            list_rect.x + 8, list_rect.y + 6 + row * row_h,
            list_rect.width - 16, row_h - 6,
        )
        active = index == game.music_room_index
        if active:
            pygame.draw.rect(game.screen, (92, 20, 34), row_rect)
            pygame.draw.rect(game.screen, config.GOLD, row_rect, 1)
            pygame.draw.polygon(game.screen, config.RED, (
                (row_rect.left + 8, row_rect.centery - 8),
                (row_rect.left + 8, row_rect.centery + 8),
                (row_rect.left + 22, row_rect.centery),
            ))
        number = game.font_small.render(
            f"No.{index + 1:02d}", True, config.MUTED
        )
        game.screen.blit(
            number, number.get_rect(midleft=(row_rect.left + 34, row_rect.centery))
        )
        title_surface = game.font.render(
            title, True, config.WHITE if active else config.MUTED
        )
        game.screen.blit(
            title_surface,
            title_surface.get_rect(midleft=(row_rect.left + 112, row_rect.centery)),
        )
        if filename == game.music_preview:
            mark = game.font_small.render("▶ 再生中", True, config.PALE_GOLD)
            game.screen.blit(
                mark, mark.get_rect(midright=(row_rect.right - 10, row_rect.centery))
            )

    # 列表滚动条：曲目多于可视行数时给出位置提示
    total = len(game.MUSIC_ROOM_TRACKS)
    if total > visible:
        bar = pygame.Rect(
            list_rect.right - 8, list_rect.y + 10, 4, list_rect.height - 20
        )
        pygame.draw.rect(game.screen, (60, 40, 40), bar)
        thumb_h = max(24, bar.height * visible // total)
        thumb_y = bar.y + (bar.height - thumb_h) * game.music_room_scroll // (
            total - visible
        )
        pygame.draw.rect(
            game.screen, config.PALE_GOLD,
            pygame.Rect(bar.x, thumb_y, bar.width, thumb_h),
        )

    # 右列：所选曲目的曲名、英文名与 ZUN 评论
    detail_rect = pygame.Rect(
        list_rect.right + 30, list_rect.y, right - (list_rect.right + 30),
        list_rect.height,
    )
    card(detail_rect)
    text_left = detail_rect.x + 26
    text_width = detail_rect.width - 52
    _, title, en_title, comment = game.MUSIC_ROOM_TRACKS[game.music_room_index]
    y = detail_rect.y + 26
    for line in game._wrap_text(title, game.font_big, text_width):
        game.screen.blit(
            game.font_big.render(line, True, config.PALE_GOLD), (text_left, y)
        )
        y += 52
    y += 6
    for line in game._wrap_text(en_title, game.font_small, text_width):
        game.screen.blit(
            game.font_small.render(line, True, config.MUTED), (text_left, y)
        )
        y += 26
    y += 10
    pygame.draw.line(
        game.screen, (120, 68, 54), (text_left, y), (text_left + text_width, y), 1
    )
    y += 26
    for paragraph in comment:
        for line in game._wrap_text(paragraph, game.font, text_width):
            game.screen.blit(
                game.font.render(line, True, config.WHITE), (text_left, y)
            )
            y += 36

    hint = "↑ ↓  選擇曲目     Enter 試聽     Tab 切換頁籤     Esc 返回標題"
    game.screen.blit(
        game.font.render(hint, True, config.WHITE),
        (left, panel.bottom - 36),
    )


def _wrap_text(game, text: str, font: pygame.font.Font,
               max_width: int) -> list[str]:
    """按像素宽度逐字折行，供音楽室的长曲名与 ZUN 评论换行使用。"""
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and font.size(candidate)[0] > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _ending_background_for_page(game, page: int) -> pygame.Surface:
    """按结局页码选择背景图：result / afterword(多页各有不同) / credits。"""
    last = len(game.ENDING_PAGES) - 1
    if page <= 0:
        return game.art.ending_victory
    if page >= last:
        return game.art.ending_credits
    afterword_index = page - 1
    if 0 <= afterword_index < len(game.AFTERWORD_PAGE_VISUALS):
        bg_key = game.AFTERWORD_PAGE_VISUALS[afterword_index][0]
        if bg_key == "scene":
            return game.art.scene_background
        if bg_key == "afterword":
            return game.art.ending_afterword
        if bg_key == "victory":
            return game.art.ending_victory
    return game.art.ending_afterword


def _draw_title_screen(game) -> None:
    game.screen.blit(game.title_background, (0, 0))
    game.screen.blit(game.title_shade, (0, 0))
    title_panel = pygame.Rect(*game.TITLE_INFO_PANEL_RECT)
    game._draw_ornate_panel(title_panel)
    left = title_panel.left + 28
    game.screen.blit(
        game.font.render("红雾异变  /  STORY 01", True, config.MUTED),
        (left, title_panel.top + 28),
    )
    game.screen.blit(
        game.font_big.render("东方红雾录", True, config.PALE_GOLD),
        (left, title_panel.top + 76),
    )
    game.screen.blit(
        game.font.render("～ Scarlet Mist Incident ～", True, config.WHITE),
        (left, title_panel.top + 132),
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, title_panel.top + 176),
        (title_panel.right - 28, title_panel.top + 176), 1,
    )
    game.screen.blit(
        game.font.render(
            "幻想乡被紅霧籠罩，",
            True, config.WHITE,
        ),
        (left, title_panel.top + 196),
    )
    game.screen.blit(
        game.font.render(
            "異變的源頭指向湖畔洋館。",
            True, config.WHITE,
        ),
        (left, title_panel.top + 230),
    )
    game.screen.blit(
        game.font.render(
            "穿越三重符卡，尋回夜色。",
            True, config.PALE_GOLD,
        ),
        (left, title_panel.top + 274),
    )
    game.screen.blit(
        game.font.render("異変退治  /  DANMAKU", True, config.MUTED),
        (left, title_panel.top + 316),
    )
    game.screen.blit(
        game.font.render("↑ / ↓ 選擇    Enter 開始", True, config.WHITE),
        (800, 424),
    )

    # 菜单：仿 TH06 原作——大字标题 + 英文小字，选中项以红色光标与金框标示。
    items = game._menu_items()
    count = len(items)
    row_h, gap = 58, 14
    block_h = count * row_h + (count - 1) * gap
    start_y = 660 - block_h // 2      # 菜单整体在右侧垂直居中
    for index, label in enumerate(items):
        y = start_y + index * (row_h + gap)
        row = pygame.Rect(786, y, 420, row_h)
        selected = index == game.menu_selection
        if selected:
            plate = pygame.Surface(row.size, pygame.SRCALPHA)
            plate.fill((92, 20, 34, 150))
            game.screen.blit(plate, row.topleft)
            pygame.draw.rect(game.screen, config.GOLD, row, 2)
            pygame.draw.rect(
                game.screen, (120, 68, 54), row.inflate(-8, -8), 1
            )
            # 原作风格的红色三角光标
            cursor = (
                (row.left - 26, row.centery - 11),
                (row.left - 26, row.centery + 11),
                (row.left - 4, row.centery),
            )
            pygame.draw.polygon(game.screen, config.RED, cursor)
        chinese = game.font_menu.render(
            label, True,
            config.WHITE if selected else config.MUTED,
        )
        game.screen.blit(
            chinese, chinese.get_rect(midleft=(row.left + 42, row.centery))
        )
        english = game.font_small.render(
            game.MENU_LABELS[label], True,
            config.PALE_GOLD if selected else (110, 92, 86),
        )
        game.screen.blit(
            english, english.get_rect(midright=(row.right - 18, row.centery + 4))
        )

    if getattr(game, "quit_confirm_active", False):
        game._draw_quit_confirm()


def _draw_quit_confirm(game, title: str = "退出游戏？",
                       body: str = "確定要離開東方紅霧録嗎？") -> None:
    """退出确认框：压暗整屏后居中弹出「是 / 否」。

    标题页用于退出程序，关卡内用于放弃本局返回标题，仅文案不同。
    """
    veil = pygame.Surface((config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA)
    veil.fill((4, 2, 6, 176))
    game.screen.blit(veil, (0, 0))

    panel = pygame.Rect(0, 0, 560, 232)
    panel.center = (config.SCREEN_W // 2, config.SCREEN_H // 2)
    game._draw_ornate_panel(panel)
    center_x = panel.centerx
    game._draw_center_text(
        title, config.PALE_GOLD, font=game.font_big,
        y=panel.top + 62, center_x=center_x,
    )
    game._draw_center_text(
        body, config.WHITE, font=game.font,
        y=panel.top + 112, center_x=center_x,
    )
    for index, label in enumerate(("是", "否")):
        selected = index == game.quit_confirm_index
        color = config.GOLD if selected else config.MUTED
        game._draw_center_text(
            f"『{label}』" if selected else f"　{label}　",
            color, font=game.font_big, y=panel.top + 166,
            center_x=center_x + (-96 if index == 0 else 96),
        )
    game._draw_center_text(
        "← →  選擇    Enter 確定    Esc 取消", config.MUTED,
        font=game.font, y=panel.bottom - 20, center_x=center_x,
    )


def _draw_manual_screen(game) -> None:
    """说明书：哥特风双线描金边框 + 页签，依次为背景、用语、操作。"""
    game.screen.blit(game.title_background, (0, 0))
    game.screen.blit(game.title_shade, (0, 0))

    frame = pygame.Rect(56, 56, config.SCREEN_W - 112, config.SCREEN_H - 112)
    pygame.draw.rect(game.screen, config.GOLD, frame, 2)
    pygame.draw.rect(game.screen, (120, 68, 54), frame.inflate(-16, -16), 1)
    inner_left = frame.left + 44
    inner_right = frame.right - 44

    subtitle = ("被染红的夏夜，与三重符卡",
                "幻想乡用语与玩法解说",
                "键位分配一览")[game.manual_page]
    heading = "幻想乡异闻 ～ Scarlet Danmaku"
    game.screen.blit(game.font_big.render(heading, True, config.PALE_GOLD),
                     (inner_left, frame.top + 34))
    game.screen.blit(game.font.render(subtitle, True, config.MUTED),
                     (inner_left, frame.top + 92))
    pygame.draw.line(
        game.screen, config.GOLD,
        (inner_left, frame.top + 132), (inner_right, frame.top + 132), 1,
    )

    # 右上角页签，当前页用绯红底、未选中页压暗
    tab_width = 150
    for index, label in enumerate(game.MANUAL_PAGES):
        tab = pygame.Rect(
            inner_right - (len(game.MANUAL_PAGES) - index) * tab_width,
            frame.top + 40, tab_width - 8, 40,
        )
        active = index == game.manual_page
        pygame.draw.rect(
            game.screen, (92, 20, 34) if active else (34, 14, 22), tab
        )
        pygame.draw.rect(game.screen, config.GOLD, tab, 1)
        text = f"{'一二三'[index]}、{label}"
        surface = game.font.render(
            text, True, config.PALE_GOLD if active else config.MUTED
        )
        game.screen.blit(surface, surface.get_rect(center=tab.center))

    if game.manual_page == 0:
        game._draw_story_page(inner_left, frame.top + 166)
    elif game.manual_page == 1:
        game._draw_terms_page(inner_left, inner_right, frame.top + 166)
    else:
        game._draw_controls_page(inner_left, inner_right, frame.top + 166)

    hint = game.font.render(
        "← → 翻阅说明页        Enter / Esc 返回标题", True, config.WHITE
    )
    game.screen.blit(hint, (inner_left, frame.bottom - 56))


def _draw_story_page(game, left: int, top: int) -> None:
    """背景说明正文：段落之间自动留白。"""
    y = top
    for line in game.MANUAL_STORY:
        if line:
            game.screen.blit(game.font.render(line, True, config.WHITE),
                             (left, y))
        y += 42


def _draw_terms_page(game, left: int, right: int, top: int) -> None:
    """用语解说：左列术语、右列释义。"""
    for index, (term, meaning) in enumerate(game.MANUAL_TERMS):
        y = top + index * 42
        game.screen.blit(game.font.render(term, True, config.PALE_GOLD),
                         (left, y))
        game.screen.blit(game.font.render(meaning, True, config.WHITE),
                         (left + 280, y))


def _draw_controls_page(game, left: int, right: int, top: int) -> None:
    """操作指南：左侧键位、右侧动作。"""
    for index, (key, action) in enumerate(game.MANUAL_KEYS):
        y = top + index * 42
        game.screen.blit(game.font.render(key, True, config.PALE_GOLD),
                         (left, y))
        game.screen.blit(game.font.render(action, True, config.WHITE),
                         (left + 250, y))

    y = top + len(game.MANUAL_KEYS) * 42 + 24
    pygame.draw.line(game.screen, (120, 68, 54), (left, y), (right, y), 1)
    note = game.font.render(
        "符卡、道具与判定点的含义，见「二、用语解说」。", True, config.MUTED
    )
    game.screen.blit(note, (left, y + 24))


def _draw_text_centered(
        game, text: str, y: int, color, font: pygame.font.Font) -> None:
    surface = font.render(text, True, color)
    center_x = config.PLAYFIELD_LEFT + config.PLAYFIELD_WIDTH // 2
    rect = surface.get_rect(center=(center_x, y))
    game.screen.blit(surface, rect)


def _draw_debug_overlay(game) -> None:
    """绘制碰撞调试层：空间网格、双层判定圆、扫掠线段与擦弹高亮。

    只读取实体状态，不修改位置或半径，因此开启调试不影响玩法结果。
    """
    field = pygame.Rect(
        config.PLAYFIELD_LEFT,
        config.PLAYFIELD_TOP,
        config.PLAYFIELD_WIDTH,
        config.PLAYFIELD_HEIGHT,
    )

    # 空间网格：与 SpatialGrid 使用的世界坐标对齐（格子以原点为基准）
    grid = pygame.Surface(field.size, pygame.SRCALPHA)
    grid_color = (*config.DEBUG_GRID_COLOR, config.DEBUG_GRID_ALPHA)
    cell = config.GRID_CELL_SIZE
    x = cell - (config.PLAYFIELD_LEFT % cell)
    while x < field.width:
        pygame.draw.line(grid, grid_color, (x, 0), (x, field.height), 1)
        x += cell
    y = cell - (config.PLAYFIELD_TOP % cell)
    while y < field.height:
        pygame.draw.line(grid, grid_color, (0, y), (field.width, y), 1)
        y += cell
    game.screen.blit(grid, field.topleft)

    # 敌弹本帧扫掠线段；已擦弹的子弹加一圈外环
    for b in game.bullets:
        pygame.draw.line(
            game.screen, config.DEBUG_SWEEP_COLOR,
            (round(b.prev_pos.x), round(b.prev_pos.y)),
            (round(b.pos.x), round(b.pos.y)), 1,
        )
        if b.grazed:
            pygame.draw.circle(
                game.screen, config.DEBUG_GRAZE_COLOR,
                (round(b.pos.x), round(b.pos.y)), round(b.radius) + 5, 1,
            )

    # Boss 命中区
    if game.boss is not None and game.boss.alive:
        pygame.draw.circle(
            game.screen, config.DEBUG_HIT_COLOR,
            (round(game.boss.pos.x), round(game.boss.pos.y)),
            round(game.boss.radius), 1,
        )

    # 玩家双层判定：外圈擦弹区、内圈命中区
    center = (round(game.player.pos.x), round(game.player.pos.y))
    pygame.draw.circle(
        game.screen, config.DEBUG_GRAZE_COLOR, center,
        round(game.player.graze_radius), 1,
    )
    pygame.draw.circle(
        game.screen, config.DEBUG_HIT_COLOR, center,
        max(1, round(game.player.radius)), 0,
    )


def _draw_center_text(
        game, text: str, color, font: pygame.font.Font | None = None,
        y: float | None = None, center_x: int | None = None) -> None:
    font = font or game.font_big
    surf = font.render(text, True, color)
    center = (
        center_x if center_x is not None
        else config.PLAYFIELD_LEFT + config.PLAYFIELD_WIDTH // 2,
        y or config.PLAYFIELD_TOP + config.PLAYFIELD_HEIGHT // 2,
    )
    shadow = font.render(text, True, config.BLACK)
    game.screen.blit(shadow, shadow.get_rect(center=(center[0] + 2, center[1] + 2)))
    rect = surf.get_rect(center=center)
    game.screen.blit(surf, rect)
