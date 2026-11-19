"""HUD 與战斗界面提示的纯绘制函数。"""
from __future__ import annotations

import math

import pygame

from . import config


def wrap_text_to_width(
        text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """按字体实际渲染宽度逐字换行，避免中英文混排时越过面板边界。"""
    lines: list[str] = []
    current = ""
    for character in text:
        if character == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + character
        if current and font.size(candidate)[0] > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current or not lines:
        lines.append(current)
    return lines


def draw_phase_hud(game) -> None:
    """弹幕场顶部的符卡条：符卡名、剩余段数与倒计时；无 Boss 时隐藏。"""
    boss = game.boss
    if boss is None or not boss.alive:
        return
    bar = pygame.Rect(config.PLAYFIELD_LEFT, config.PLAYFIELD_TOP,
                      config.PLAYFIELD_WIDTH, 40)
    shade = pygame.Surface(bar.size, pygame.SRCALPHA)
    shade.fill((7, 3, 9, 160))
    game.screen.blit(shade, bar.topleft)
    pygame.draw.line(
        game.screen, config.GOLD, bar.bottomleft, bar.bottomright, 1
    )

    total = boss.spell_count
    phase = min(boss.phase, total)
    game.screen.blit(
        game.font.render(boss.spell.name, True, config.PALE_GOLD),
        (bar.left + 16, bar.top + 7),
    )

    # 剩余段数：已过的段位画成空心，未过的画成实心
    remaining = total - phase + 1
    marker_x = bar.left + 380
    for index in range(total):
        center = (marker_x + index * 26, bar.centery)
        if index < remaining:
            pygame.draw.circle(game.screen, config.RED, center, 7)
            pygame.draw.circle(game.screen, config.PALE_GOLD, center, 7, 1)
        else:
            pygame.draw.circle(game.screen, config.GRAY, center, 7, 1)

    seconds = max(0.0, game.phase_timer)
    timer = game.font.render(f"{seconds:05.2f}", True, config.WHITE)
    game.screen.blit(timer, timer.get_rect(midright=(bar.right - 16, bar.centery)))
    # 符卡取得数：本轮已经完整避开、未用灵击而破开的符卡张数
    captured = game.font.render(
        f"取得 {game.spells_captured}", True, config.PALE_GOLD
    )
    game.screen.blit(
        captured, captured.get_rect(midright=(bar.right - 108, bar.centery))
    )

def draw_power_up_banner(game) -> None:
    """自机火力升档时，在自机上方短暂浮出提示，让成长看得见。"""
    if game.power_up_timer <= 0.0:
        return
    total = max(0.001, config.POWER_UP_BANNER_DURATION)
    remaining = game.power_up_timer
    fade_in = min(1.0, (total - remaining) / 0.15)
    fade_out = min(1.0, remaining / 0.35)
    alpha = int(255 * min(fade_in, fade_out))

    center = (round(game.player.pos.x), round(game.player.pos.y) - 84)
    shadow = game.font.render(game.power_up_text, True, config.BLACK)
    shadow.set_alpha(alpha)
    text = game.font.render(game.power_up_text, True, config.PALE_GOLD)
    text.set_alpha(alpha)
    game.screen.blit(
        shadow, shadow.get_rect(center=(center[0] + 2, center[1] + 2))
    )
    game.screen.blit(text, text.get_rect(center=center))

def draw_spell_announcement(game) -> None:
    """符卡展开时的播报卡片：符卡名 + 技能描述，渐入渐出。"""
    boss = game.boss
    if boss is None or not boss.alive:
        return
    if game.spell_announce_timer <= 0.0:
        return
    spell = boss.spell
    if not spell.flavor and not spell.name:
        return

    field = pygame.Rect(
        config.PLAYFIELD_LEFT, config.PLAYFIELD_TOP,
        config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT,
    )
    # 后 0.5 秒淡出
    total = max(0.001, config.SPELL_ANNOUNCE_DURATION)
    fade_in = min(1.0, (total - game.spell_announce_timer) / 0.3)
    fade_out = min(1.0, game.spell_announce_timer / 0.5)
    alpha = int(255 * min(fade_in, fade_out))

    label = game.font.render(
        f"第 {min(boss.phase, boss.spell_count)} 符卡  /  SPELL CARD",
        True, config.MUTED,
    )
    name = game.font_big.render(spell.name, True, config.PALE_GOLD)
    desc_lines = wrap_text_to_width(
        spell.flavor, game.font, field.width - 56
    ) if spell.flavor else []
    label_y = 12
    name_y = 38
    desc_y = max(84, name_y + name.get_height() + 6)
    card_h = max(
        116,
        desc_y + len(desc_lines) * game.font.get_linesize() + 12,
    )
    card = pygame.Rect(
        field.left, field.centery - card_h // 2, field.width, card_h
    )
    shade = pygame.Surface(card.size, pygame.SRCALPHA)
    shade.fill((8, 3, 12, int(220 * min(1.0, fade_in))))
    game.screen.blit(shade, card.topleft)
    pygame.draw.line(game.screen, config.GOLD, card.topleft, card.topright, 2)
    pygame.draw.line(game.screen, config.GOLD, card.bottomleft,
                     card.bottomright, 2)

    label.set_alpha(alpha)
    game.screen.blit(label, (card.left + 28, card.top + label_y))

    name.set_alpha(alpha)
    game.screen.blit(name, (card.left + 28, card.top + name_y))

    for index, line in enumerate(desc_lines):
        desc = game.font.render(line, True, config.WHITE)
        desc.set_alpha(alpha)
        game.screen.blit(
            desc,
            (card.left + 28, card.top + desc_y
             + index * game.font.get_linesize()),
        )

def draw_charge_aura(game, entity, special) -> None:
    """蓄力光环：随蓄力进度放大、增亮并缓慢旋转，提示技能即将发动。

    ``special`` 为 None 表示自机技能（用玩家光环与剩余时间），否则用该
    技能的贴图与 Boss 蓄力剩余时间。
    """
    if special is not None:
        total = max(0.001, special.charge)
        remaining = game.boss_skill_timer
        sprite = game.art.skill_sprites.get(special.sprite_key)
    else:
        total = max(0.001, config.PLAYER_SKILL_CHARGE_TIME)
        remaining = game.skill_timer
        sprite = game.art.skill_sprites.get("skill_player")
    if sprite is None:
        return
    progress = min(1.0, max(0.0, 1.0 - remaining / total))
    # 由小到大再轻微脉动，形成「吸气 → 收束」的蓄力节奏
    scale = 0.7 + 0.9 * progress + 0.08 * math.sin(progress * math.pi * 6)
    base = max(sprite.get_width(), sprite.get_height())
    size = max(16, round(base * scale))
    aura = pygame.transform.smoothscale(sprite, (size, size))
    aura.set_alpha(int(70 + 175 * progress))
    aura = pygame.transform.rotate(aura, 60.0 * progress)
    center = (round(entity.pos.x), round(entity.pos.y))
    game.screen.blit(aura, aura.get_rect(center=center))

def draw_boss_skill_announcement(game) -> None:
    """Boss 特殊技能发动时的播报卡片：技能名，渐入渐出。"""
    if game.boss_skill_announce_timer <= 0.0:
        return
    boss = game.boss
    special = boss.spec.special if boss is not None else None
    if special is None:
        return

    field = pygame.Rect(
        config.PLAYFIELD_LEFT, config.PLAYFIELD_TOP,
        config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT,
    )
    total = max(0.001, config.SPELL_ANNOUNCE_DURATION)
    fade_in = min(1.0, (total - game.boss_skill_announce_timer) / 0.3)
    fade_out = min(1.0, game.boss_skill_announce_timer / 0.5)
    alpha = int(255 * min(fade_in, fade_out))

    card_h = 96
    card_top = (
        field.top + 56
        if game.spell_announce_timer > 0.0
        else field.centery - card_h // 2
    )
    card = pygame.Rect(
        field.left, card_top, field.width, card_h
    )
    shade = pygame.Surface(card.size, pygame.SRCALPHA)
    shade.fill((16, 3, 8, int(220 * min(1.0, fade_in))))
    game.screen.blit(shade, card.topleft)
    pygame.draw.line(game.screen, config.RED, card.topleft, card.topright, 2)
    pygame.draw.line(game.screen, config.RED, card.bottomleft,
                     card.bottomright, 2)

    label = game.font.render("特殊技能  /  SPECIAL SKILL", True, config.MUTED)
    label.set_alpha(alpha)
    game.screen.blit(label, (card.left + 28, card.top + 14))

    name = game.font_big.render(
        game.boss_skill_announce_name, True, config.PALE_GOLD
    )
    name.set_alpha(alpha)
    game.screen.blit(name, (card.left + 28, card.top + 40))

def draw_hud(game) -> None:
    panel = pygame.Rect(
        config.PLAYFIELD_RIGHT + 32,
        config.PLAYFIELD_TOP,
        config.SCREEN_W - config.PLAYFIELD_RIGHT - 64,
        config.PLAYFIELD_HEIGHT,
    )
    game.screen.blit(game.panel_shade, panel.topleft)
    pygame.draw.rect(game.screen, config.GOLD, panel, 2)
    field = pygame.Rect(
        config.PLAYFIELD_LEFT,
        config.PLAYFIELD_TOP,
        config.PLAYFIELD_WIDTH,
        config.PLAYFIELD_HEIGHT,
    )
    pygame.draw.rect(game.screen, config.GOLD, field, 2)
    pygame.draw.line(
        game.screen, config.GOLD,
        (config.PLAYFIELD_RIGHT + 16, config.PLAYFIELD_TOP + 24),
        (config.PLAYFIELD_RIGHT + 16, config.PLAYFIELD_BOTTOM - 24),
        1,
    )

    left = panel.left + 24
    right = panel.right - 24
    script = game.director.script
    stage_no = min(max(game.director.stage_number, 1), config.STAGE_COUNT)
    game.screen.blit(
        game.font_big.render(
            script.title if script is not None else "幻想郷", True,
            config.PALE_GOLD,
        ),
        (left, panel.top + 24),
    )
    game.screen.blit(
        game.font.render(
            f"STAGE {stage_no:02d}  /  {config.STAGE_COUNT}", True,
            config.MUTED,
        ),
        (left + 2, panel.top + 78),
    )
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 120), (right, panel.top + 120), 1,
    )

    # 计分区：最高分与当前得分，均右对齐
    for index, (label, value) in enumerate((
        ("HISCORE", game.hiscore), ("SCORE", game.score),
    )):
        y = panel.top + 134 + index * 34
        game.screen.blit(game.font.render(label, True, config.MUTED), (left, y))
        value_surface = game.font.render(str(value), True, config.WHITE)
        game.screen.blit(value_surface, value_surface.get_rect(topright=(right, y)))
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 206), (right, panel.top + 206), 1,
    )

    boss = game.boss
    game.screen.blit(
        game.font.render(
            boss.spec.title if boss is not None else "雜兵波次",
            True, config.PALE_GOLD,
        ),
        (left, panel.top + 218),
    )
    phase_text = game.font.render(
        f"{min(boss.phase, boss.spell_count)} / {boss.spell_count}"
        if boss is not None else "- / -",
        True, config.WHITE,
    )
    game.screen.blit(phase_text, phase_text.get_rect(topright=(right, panel.top + 218)))
    if boss is not None:
        portrait = game._boss_sprite(boss)
        game.screen.blit(portrait, portrait.get_rect(topright=(right, panel.top + 250)))

    health_ratio = (
        max(0.0, boss.phase_hp / boss.phase_max_hp)
        if boss is not None and boss.phase_max_hp > 0.0 else 0.0
    )
    game.screen.blit(
        game.font.render("生命值  /  HP", True, config.MUTED),
        (left, panel.top + 434),
    )
    if boss is not None:
        phase_hp_text = game.font.render(
            f"{boss.phase_hp:.0f} / {boss.phase_max_hp:.0f}",
            True, config.WHITE,
        )
        game.screen.blit(
            phase_hp_text,
            phase_hp_text.get_rect(topright=(right, panel.top + 434)),
        )
    health_bar = pygame.Rect(left, panel.top + 460, panel.width - 48, 18)
    pygame.draw.rect(game.screen, (47, 19, 28), health_bar)
    fill = health_bar.inflate(-4, -4)
    fill.width = round(fill.width * health_ratio)
    if fill.width > 0:
        pygame.draw.rect(game.screen, config.RED, fill)
    pygame.draw.rect(game.screen, config.GOLD, health_bar, 1)
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 504), (right, panel.top + 504), 1,
    )

    game.screen.blit(
        game.font.render("残机  /  LIVES", True, config.PALE_GOLD),
        (left, panel.top + 516),
    )
    icon_y = panel.top + 506
    icon_x = right - 94
    for index in range(config.PLAYER_LIVES):
        icon = game.art.player_icon.copy()
        icon.set_alpha(255 if index < game.lives else 60)
        game.screen.blit(icon, (icon_x + index * 30, icon_y))
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, panel.top + 560), (right, panel.top + 560), 1,
    )

    rows = (
        ("擦弹  /  GRAZE", game.graze_total),
        ("敌弹  /  BULLETS", len(game.bullets)),
        ("命中  /  HITS", game.hit_total),
        ("灵击  /  BOMB", f"{game.bombs} / {config.PLAYER_BOMB_MAX}"),
    )
    for index, (label, value) in enumerate(rows):
        y = panel.top + 562 + index * 32
        game.screen.blit(game.font.render(label, True, config.MUTED), (left, y))
        value_surface = game.font.render(str(value), True, config.WHITE)
        game.screen.blit(value_surface, value_surface.get_rect(topright=(right, y)))

    # 火力：标签与数值同行，进度条独占下一行（避免与标签重叠）
    power_y = panel.top + 690
    game.screen.blit(
        game.font.render("火力  /  POWER", True, config.MUTED),
        (left, power_y),
    )
    power_value = game.font.render(f"{game.power:.2f}", True, config.WHITE)
    game.screen.blit(
        power_value, power_value.get_rect(topright=(right, power_y))
    )
    power_bar = pygame.Rect(left, power_y + 30, panel.width - 48, 10)
    pygame.draw.rect(game.screen, (47, 19, 28), power_bar)
    power_fill = power_bar.inflate(-4, -4)
    power_fill.width = round(
        power_fill.width * min(1.0, game.power / config.ITEM_POWER_MAX)
    )
    if power_fill.width > 0:
        pygame.draw.rect(game.screen, config.GOLD, power_fill)
    pygame.draw.rect(game.screen, config.GOLD, power_bar, 1)

    item_y = panel.top + 736
    game.screen.blit(
        game.font.render("道具  /  ITEM", True, config.MUTED), (left, item_y)
    )
    item_value = game.font.render(str(game.item_total), True, config.WHITE)
    game.screen.blit(item_value, item_value.get_rect(topright=(right, item_y)))

    divider_y = panel.top + 766
    pygame.draw.line(
        game.screen, config.GOLD,
        (left, divider_y), (right, divider_y), 1,
    )
    game.screen.blit(
        game.font.render(
            "调  试  /  DEBUG" if game.debug_overlay else "操  作  /  CONTROL",
            True, config.PALE_GOLD,
        ),
        (left, divider_y + 16),
    )
    if game.god_mode:
        badge = pygame.Rect(right - 96, divider_y + 14, 96, 26)
        pygame.draw.rect(game.screen, (92, 20, 34), badge)
        pygame.draw.rect(game.screen, config.GOLD, badge, 1)
        status = game.font.render("GOD ON", True, config.PALE_GOLD)
        game.screen.blit(status, status.get_rect(center=badge.center))
    if game.debug_overlay:
        stats = game.debug_stats
        debug_rows = (
            ("候选 / CAND", stats["candidates"]),
            ("扫掠 / SWEPT", stats["sweeps"]),
            ("Boss 命中 / HIT", stats["boss_hits"]),
        )
        for index, (label, value) in enumerate(debug_rows):
            y = divider_y + 60 + index * 34
            game.screen.blit(
                game.font.render(label, True, config.MUTED), (left, y)
            )
            value_surface = game.font.render(str(value), True, config.WHITE)
            game.screen.blit(
                value_surface, value_surface.get_rect(topright=(right, y))
            )
        return

    hints = (
        "方向键 / WASD   移动",
        "Shift 低速   F3 作弊   F1 暂停",
        "Z 射击  X 灵击  C 特技",
    )
    for index, hint in enumerate(hints):
        game.screen.blit(
            game.font.render(hint, True, config.WHITE),
            (left, divider_y + 46 + index * 28),
        )
