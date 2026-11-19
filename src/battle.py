"""Battle updates and combat mechanics operating on a Game instance."""
from __future__ import annotations

import math
import random

import pygame
from pygame.math import Vector2

from . import collision, config, spells
from .director import BANNER, TALK
from .entities import Boss, BossBeam, Bullet, Effect, Fairy, Item, PlayerShot


def _power_tier(game) -> int:
    """当前火力档位（1 起）：单发 → 双发 → 三发 → 满火力四发。"""
    tier = 1
    for index, (threshold, _) in enumerate(config.POWER_TIERS):
        if game.power >= threshold:
            tier = index + 1
    return tier


def _shot_offsets(game) -> tuple[float, ...]:
    """按当前火力返回自机弹的横向偏移。"""
    return config.POWER_TIERS[game._power_tier() - 1][1]


def _player_shot_sprite(game) -> pygame.Surface:
    """按火力档位取自机弹贴图：档位越高，弹体越大、配色越亮。"""
    return game.art.player_shots[f"lv{game._power_tier()}"]


def _player_shot_trail(game) -> pygame.Surface:
    """按火力档位取自机弹的拖尾贴图（弹体 + 彗尾的整图）。"""
    return game.art.player_shot_trails[f"lv{game._power_tier()}"]


def _power_stage_curve(game) -> tuple[float, float]:
    """当前关卡的 (保底火力, 时间成长上限)。"""
    index = min(
        max(0, game.director.stage_number - 1),
        len(config.POWER_STAGE_CURVE) - 1,
    )
    return config.POWER_STAGE_CURVE[index]


def _update_power_growth(game, dt: float) -> None:
    """战斗中火力随时间自动成长，但不会超过当前关卡的上限。"""
    game.power_time += dt
    while game.power_time >= config.POWER_TIME_STEP_SECONDS:
        game.power_time -= config.POWER_TIME_STEP_SECONDS
        game._add_power(
            config.POWER_GAIN_STEP, cap=game._power_stage_curve()[1]
        )


def _add_power(game, amount: float, cap: float | None = None) -> None:
    """增加火力；跨过档位时浮出提示。

    ``cap`` 是本次成长的上限：时间成长受当前关卡上限约束，红玉不设限，
    所以抢红玉可以提前突破关卡节奏。数值本身在侧栏「火力 / POWER」
    一行即时可见，提示只在档位变化时出现，避免刷屏。
    """
    limit = config.ITEM_POWER_MAX
    if cap is not None:
        limit = min(cap, limit)
    if game.power >= limit:
        return
    before = game._power_tier()
    game.power = min(limit, game.power + amount)
    after = game._power_tier()
    if after > before:
        game.power_up_timer = config.POWER_UP_BANNER_DURATION
        game.power_up_text = (
            f"火力上昇 · {after} 段  /  POWER UP"
            if after < len(config.POWER_TIERS)
            else "火力全開  /  FULL POWER"
        )
        game.audio.play("menu_ok")


def _spawn_player_shots(game, dt: float) -> None:
    """按住射击键时按固定间隔发射玩家弹；弹数随火力提升。"""
    game.fire_timer = max(0.0, game.fire_timer - dt)
    if game.shooting and game.fire_timer <= 0.0:
        muzzle_y = game.player.pos.y - game.player.radius
        for offset in game._shot_offsets():
            game.player_shots.append(
                PlayerShot(game.player.pos.x + offset, muzzle_y)
            )
        game.audio.play("shot")
        game.fire_timer = config.PLAYER_FIRE_INTERVAL


def _boss_attack_origin(game, boss: Boss) -> Vector2:
    """返回立绘身体处的弹幕发射点，区别于 Boss 立绘的脸部中心。"""
    return boss.pos + Vector2(*config.BOSS_ATTACK_ORIGIN_OFFSET)


def _spawn_boss(game, spec) -> None:
    """按 director 给出的规格生成 Boss，并复位符卡计时。"""
    game.boss = Boss(config.BOSS_START_X, config.BOSS_START_Y, spec)
    game.boss_beams.clear()
    game.boss_attack_phase = 0
    game.spell_timers = []
    game.phase_timer = config.BOSS_PHASE_TIME_LIMIT
    game.boss_flash = 0.0
    game.spell_imperilled = False
    game.spell_timed_out = False
    game.spell_announce_timer = 0.0
    game.boss_skill_next_hp = config.BOSS_SKILL_FIRST_HP
    game.boss_skill_timer = 0.0
    game.boss_skill_recover = 0.0
    game.boss_skill_announce_timer = 0.0


def _spawn_boss_attack(game, boss: Boss, emitter) -> None:
    """铺开一个发射器描述的一轮弹幕。

    形状与角度交给 :func:`spells.emit`，这里只把结果并入弹幕列表，并在
    带有 ``spin`` 的环形 / 螺旋上累加整体相位，让弹幕逐轮旋转起来。
    """
    origin = game._boss_attack_origin(boss)
    game.bullets.extend(spells.emit(
        emitter, game.art, origin, game.player.pos, boss.spell_angle
    ))
    if emitter.spin:
        boss.spell_angle = (
            boss.spell_angle + math.radians(emitter.spin)
        ) % math.tau


def _update_boss_attacks(game, dt: float) -> None:
    """推进当前符卡：各发射器独立冷却，限时耗尽则强制结束本张符卡。"""
    boss = game.boss
    if boss is None or not boss.alive:
        return

    spell = boss.spell
    if boss.phase != game.boss_attack_phase:
        game._enter_spell(boss, spell, game.phase_timer)

    game.phase_timer = max(0.0, game.phase_timer - dt)
    if game.phase_timer <= 0.0:
        game._force_phase_end()
        return

    if game._update_boss_skill(dt):
        return          # 技能期间 Boss 不放符卡弹幕

    for index, emitter in enumerate(spell.emitters):
        game.spell_timers[index] -= dt
        if game.spell_timers[index] > 0.0:
            continue
        game._spawn_boss_attack(boss, emitter)
        game.spell_timers[index] = emitter.interval


def _update_boss_skill(game, dt: float) -> bool:
    """推进 Boss 的特殊技能，返回 True 表示 Boss 正忙于技能。

    技能按「血量分档」发动：血量每跌破一个阈值就发动一次，而阈值间距逐次
    收窄，因此血量越低发动得越频繁。蓄力阶段是给玩家的预告（Boss 不放
    符卡弹幕），释放时铺开一圈专属弹幕，之后留一段后摇作为玩家的反击窗口。
    """
    boss = game.boss
    if boss is None:
        return False
    special = boss.spec.special
    if special is None:
        return False
    if game.boss_skill_timer > 0.0:
        game.boss_skill_timer = max(0.0, game.boss_skill_timer - dt)
        if game.boss_skill_timer <= 0.0:
            game._release_boss_skill(boss, special)
            game.boss_skill_recover = special.recover
        return True
    if game.boss_skill_recover > 0.0:
        game.boss_skill_recover = max(0.0, game.boss_skill_recover - dt)
        return True
    # 血量跌破当前档位、且符卡名播报已结束时发动；下次所需血量按比例下移
    ratio = boss.hp / boss.max_hp if boss.max_hp > 0.0 else 0.0
    if ratio <= game.boss_skill_next_hp and game.spell_announce_timer <= 0.0:
        game.boss_skill_next_hp *= config.BOSS_SKILL_HP_FACTOR
        game.boss_skill_timer = special.charge
        game.audio.play("alert")
        return True
    return False


def _release_boss_skill(game, boss: Boss, special) -> None:
    """Boss 特殊技能发动：释放专属非环形弹幕与激光阵列。"""
    origin = game._boss_attack_origin(boss)
    for emitter in special.emitters:
        game.bullets.extend(spells.emit(
            emitter, game.art, origin, game.player.pos
        ))
    delta = game.player.pos - origin
    aim_angle = (
        math.atan2(delta.y, delta.x)
        if delta.length_squared() else math.pi / 2
    )
    for pattern in special.beams:
        angle = aim_angle + math.radians(pattern.angle_offset)
        perpendicular = Vector2(-math.sin(angle), math.cos(angle))
        beam_origin = origin + perpendicular * pattern.parallel_offset
        game.boss_beams.append(BossBeam(
            beam_origin.x, beam_origin.y, angle,
            pattern.length, pattern.width, pattern.telegraph,
            pattern.duration, pattern.color,
        ))
    game.effects.append(Effect(
        boss.pos.x, boss.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.25, end_scale=2.1,
    ))
    # 主题冲击波为高密度弹幕和不同几何的光束预热。
    aura = game.art.skill_sprites.get(special.sprite_key)
    if aura is not None:
        base = max(1, aura.get_width())
        game.effects.append(Effect(
            boss.pos.x, boss.pos.y, aura,
            config.SKILL_SHOCKWAVE_DURATION,
            start_scale=0.5, end_scale=special.radius * 2.0 / base,
            start_alpha=210, end_alpha=0,
        ))
    game.screen_shake = max(game.screen_shake, config.SKILL_SHAKE * 1.5)
    game.skill_flash = config.BOSS_SKILL_FLASH
    game.skill_overlay.fill((*special.flash_color, 255))
    game.audio.play("enemy_dead")
    game.boss_skill_announce_name = special.name
    game.boss_skill_announce_timer = config.SPELL_ANNOUNCE_DURATION


def _enter_spell(game, boss: Boss, spell, remaining: float) -> None:
    """切换到一张符卡：结算上一张的成败，重置计时并按需掉落道具。

    ``remaining`` 是被终结的那张符卡的剩余时间，用于计算时间加成；首张
    符卡没有「上一张」，因此不结算。
    """
    previous = game.boss_attack_phase
    game.boss_attack_phase = boss.phase
    game.spell_timers = spell.cooldowns()
    game.phase_timer = spell.duration
    boss.spell_angle = 0.0
    # 展开新符卡时弹出符卡名与技能描述，贴近原作的符卡宣告
    game.spell_announce_timer = config.SPELL_ANNOUNCE_DURATION
    if previous <= 0:
        return
    game._settle_spell(remaining)
    game.audio.play("phase_change")
    game.effects.append(Effect(
        boss.pos.x, boss.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.3, end_scale=1.0,
    ))
    # 每展开一张新符卡掉一批火力道具；最后一张额外给一个 1UP
    game._spawn_items(
        boss.pos.x, boss.pos.y, "power", config.BOSS_PHASE_DROP_POWER
    )
    if boss.phase == boss.spell_count:
        game._spawn_items(boss.pos.x, boss.pos.y + 44.0, "life", 1)


def _settle_spell(game, remaining: float) -> None:
    """结算刚结束的一张符卡。

    原作规则：只有在限时内、且全程未被击中也没用灵击，才算「取得」并拿到
    时间加成；被击中、灵击或超时都记为失败，不给分。
    """
    if game.spell_imperilled or game.spell_timed_out:
        game.spells_failed += 1
        game.audio.play("menu_cancel")
    else:
        game.spells_captured += 1
        game.score += (config.BOSS_SPELL_BASE_BONUS
                       + config.BOSS_SPELL_TIME_BONUS
                       * int(max(0.0, remaining)))
        game.audio.play("menu_ok")
    game.spell_imperilled = False
    game.spell_timed_out = False


def _force_phase_end(game) -> None:
    """符卡倒计时归零：把当前符卡直接推到尽头。

    非最后一张超时即降到本段末尾（转入下一张），最后一张超时视为 Boss
    被击破，与原作「符卡时间到即结束该符卡」的处理一致；超时不结算取得。
    """
    boss = game.boss
    if boss is None:
        return
    game.spell_timed_out = True
    spell_count = boss.spell_count
    if boss.phase < spell_count:
        next_phases_hp = sum(
            spell.hp for spell in boss.spec.spells[boss.phase:]
        )
        boss.hp = min(
            boss.hp, next_phases_hp - 1.0
        )
        game.phase_timer = 0.0
    else:
        boss.hp = 0.0
        boss.alive = False


def _check_boss_collisions(game) -> None:
    """用相对运动线段检测玩家弹与移动 Boss 的碰撞。"""
    if game.boss is not None and game.boss.alive:
        for shot in game.player_shots:
            if not shot.alive:
                continue
            game.debug_stats["boss_sweeps"] += 1
            x1 = shot.prev_pos.x - game.boss.prev_pos.x
            y1 = shot.prev_pos.y - game.boss.prev_pos.y
            x2 = shot.pos.x - game.boss.pos.x
            y2 = shot.pos.y - game.boss.pos.y
            if collision.segment_circle(
                    x1, y1, x2, y2, 0.0, 0.0,
                    shot.radius + game.boss.radius):
                shot.alive = False
                game.debug_stats["boss_hits"] += 1
                game.boss.take_damage(shot.damage)
                game.boss_flash = config.BOSS_FLASH_DURATION
                game.audio.play("enemy_hit")
                game.screen_shake = max(
                    game.screen_shake, config.HIT_SPARK_SHAKE
                )
                game.effects.append(Effect(
                    shot.pos.x, shot.pos.y, game.art.hit_spark,
                    config.HIT_SPARK_DURATION, start_scale=0.7,
                    end_scale=config.HIT_SPARK_END_SCALE,
                ))
                if not game.boss.alive:
                    break

    game.player_shots = [shot for shot in game.player_shots if shot.alive]
    if game.boss is not None and not game.boss.alive:
        game._on_boss_defeated()


def _check_fairy_collisions(game) -> None:
    """玩家弹与可击破妖精的扫掠判定；击破后按掉落表生成道具。"""
    if not game.fairies:
        return
    for shot in game.player_shots:
        if not shot.alive:
            continue
        for fairy in game.fairies:
            if not fairy.alive:
                continue
            x1 = shot.prev_pos.x - fairy.prev_pos.x
            y1 = shot.prev_pos.y - fairy.prev_pos.y
            x2 = shot.pos.x - fairy.pos.x
            y2 = shot.pos.y - fairy.pos.y
            if collision.segment_circle(
                    x1, y1, x2, y2, 0.0, 0.0,
                    shot.radius + fairy.radius):
                shot.alive = False
                fairy.take_damage(shot.damage)
                fairy.hit_flash = config.BOSS_FLASH_DURATION
                game.audio.play("enemy_hit")
                game.screen_shake = max(
                    game.screen_shake, config.HIT_SPARK_SHAKE
                )
                game.effects.append(Effect(
                    shot.pos.x, shot.pos.y, game.art.hit_spark,
                    config.HIT_SPARK_DURATION, start_scale=0.7,
                    end_scale=config.HIT_SPARK_END_SCALE,
                ))
                if not fairy.alive:
                    game._on_fairy_defeated(fairy)
                break

    game.player_shots = [shot for shot in game.player_shots if shot.alive]
    game.fairies = [fairy for fairy in game.fairies if fairy.alive]


def _on_fairy_defeated(game, fairy: Fairy) -> None:
    """击破妖精：按波次指定掉落，缺省时轮换 POINT/POWER 并低概率掉 LIFE。"""
    game.audio.play("enemy_dead")
    game.effects.append(Effect(
        fairy.pos.x, fairy.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.14, end_scale=0.36,
        start_alpha=200, end_alpha=0,
    ))
    game.fairy_kill_count += 1
    if fairy.drop is not None:
        kind = fairy.drop
    elif random.random() < config.FAIRY_LIFE_DROP_CHANCE:
        kind = "life"
    else:
        pattern = config.FAIRY_DROP_PATTERN
        kind = pattern[(game.fairy_kill_count - 1) % len(pattern)]
    game._spawn_items(
        fairy.pos.x, fairy.pos.y, kind, config.FAIRY_POINT_DROPS
    )


def _spawn_items(game, x: float, y: float, kind: str, count: int) -> None:
    """在 (x, y) 附近撒出若干道具，避免彼此完全重叠。"""
    for _ in range(max(0, count)):
        game.items.append(Item(
            x + random.uniform(-36.0, 36.0),
            y + random.uniform(-18.0, 18.0),
            kind,
            sprite=game.art.item_sprites[kind],
        ))


def _collect_item(game, item: Item) -> None:
    """拾取道具：按种类增加火力 / 分数 / 残机。"""
    item.alive = False
    game.item_total += 1
    if item.kind == "power":
        if game.power >= config.ITEM_POWER_MAX:
            game.score += config.ITEM_POWER_FULL_SCORE
        else:
            game._add_power(config.POWER_GAIN_PICKUP)
    elif item.kind == "point":
        game.score += config.ITEM_POINT_SCORE
    elif item.kind == "life":
        game.lives = min(config.PLAYER_LIVES, game.lives + 1)
    game.audio.play("menu_ok")


def _update_items(game, dt: float) -> None:
    """推进道具：靠近自机时磁吸，越过回收线时全屏吸入，接触后拾取。"""
    collect_all = game.player.pos.y <= config.ITEM_COLLECT_LINE
    for item in game.items:
        if not item.alive:
            continue
        offset = game.player.pos - item.pos
        distance = offset.length()
        if distance == 0.0:
            item.vel = Vector2(0.0, 0.0)
        elif collect_all or distance <= config.ITEM_MAGNET_RADIUS:
            item.vel = offset * (config.ITEM_MAGNET_SPEED / distance)
        else:
            item.vel = Vector2(0.0, config.ITEM_FALL_SPEED)
        item.update(dt)
        if item.alive and item.pos.distance_to(game.player.pos) <= item.radius:
            game._collect_item(item)
    game.items = [item for item in game.items if item.alive]


def _on_boss_defeated(game) -> None:
    """击破 Boss：结算符卡与分数、播放大爆特效并清空弹幕，随后回报 director。

    中 Boss 只是关卡中的一道关卡，击破后立刻让出场地；关底 Boss 击破后
    由 director 接手推进后续对话、关卡结算与结局。最终关的关底 Boss 击破
    时会触发一段「异变终结」仪式：白闪、震屏、慢动作粒子与大字卡，
    推迟 director 的推进直到仪式播完。
    """
    boss = game.boss
    if boss is None:
        return
    # 最后一张符卡在「换符卡」时不会被结算，这里补上
    game._settle_spell(game.phase_timer)
    game.score += (config.MIDBOSS_SCORE if boss.midboss
                   else config.VICTORY_SCORE)
    game.audio.play("enemy_dead")
    game.effects.append(Effect(
        boss.pos.x, boss.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.4, end_scale=1.3,
    ))
    game.bullets.clear()
    getattr(game, "boss_beams", []).clear()
    game.player_shots.clear()
    game.boss = None
    game.spell_timers = []
    game.phase_timer = config.BOSS_PHASE_TIME_LIMIT
    game._register_hiscore()

    is_final_boss = (
        not boss.midboss
        and game.director.stage_number >= config.STAGE_COUNT
    )
    if is_final_boss:
        # 最终 Boss 击破仪式：环形爆发 + 多段闪光 + 强震屏
        cx, cy = boss.pos.x, boss.pos.y
        ring_count = 10
        for i in range(ring_count):
            angle = 2.0 * math.pi * i / ring_count
            radius = 70.0
            game.effects.append(Effect(
                cx + math.cos(angle) * radius,
                cy + math.sin(angle) * radius,
                game.art.boss_burst, config.BURST_DURATION * 1.8,
                start_scale=0.4, end_scale=2.4,
            ))
        for offset in ((-60, -30), (60, -20), (0, 40), (-40, 50), (50, 30)):
            game.effects.append(Effect(
                boss.pos.x + offset[0], boss.pos.y + offset[1],
                game.art.boss_burst, config.BURST_DURATION * 1.6,
                start_scale=0.5, end_scale=2.2,
            ))
        game.boss_ceremony_timer = 3.6
        game.screen_shake = 18.0
        return
    director = getattr(game, "director", None)
    if director is not None:
        director.notify_boss_defeated()


def _use_bomb(game) -> None:
    """灵击（Bomb）：消耗一枚符卡，清去身边弹幕并获得短暂无敌。

    与「被击中即清屏」不同，这是玩家主动的保命手段：消去的子弹会折算
    分数，并少量化作点数道具，用来换取有限的火力补给。
    """
    if (game.bombs <= 0
            or game.bomb_timer > config.PLAYER_BOMB_REUSE_GAP
            or game.game_over or game.victory or game.paused):
        return
    game.bombs -= 1
    game.bomb_timer = config.PLAYER_BOMB_DURATION
    game.invulnerable_timer = max(
        game.invulnerable_timer, config.PLAYER_BOMB_DURATION
    )
    # 用灵击保命，代价是当前符卡失去「取得」资格
    game.spell_imperilled = True
    game.audio.play("phase_change")
    game.effects.append(Effect(
        game.player.pos.x, game.player.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.25, end_scale=1.7,
        start_alpha=190, end_alpha=0,
    ))
    cleared, kept = 0, []
    for bullet in game.bullets:
        if bullet.pos.distance_to(game.player.pos) <= config.PLAYER_BOMB_RADIUS:
            cleared += 1
        else:
            kept.append(bullet)
    game.bullets = kept
    game.score += cleared * config.PLAYER_BOMB_BULLET_SCORE
    drops = min(cleared // 4, config.PLAYER_BOMB_CLEAR_ITEM_CAP)
    if drops > 0:
        game._spawn_items(
            game.player.pos.x, game.player.pos.y, "point", drops
        )


def _recharge_bombs(game, dt: float) -> None:
    """按时间自动回复符卡：每 PLAYER_BOMB_RECHARGE 秒回复 1 枚，封顶 MAX。"""
    if game.bombs < config.PLAYER_BOMB_MAX:
        game.bomb_charge += dt
        if game.bomb_charge >= config.PLAYER_BOMB_RECHARGE:
            game.bomb_charge -= config.PLAYER_BOMB_RECHARGE
            game.bombs += 1
    else:
        game.bomb_charge = 0.0


def _use_player_skill(game) -> None:
    """C 键：发动自机特殊技能，先蓄力再释放；蓄力中不可重复触发。"""
    if (game.skill_state != "ready" or game.game_over or game.victory
            or game.paused or game.director.state in (BANNER, TALK)):
        return
    game.skill_state = "charge"
    game.skill_timer = config.PLAYER_SKILL_CHARGE_TIME
    game.audio.play("alert")


def _release_player_skill(game) -> None:
    """释放自机技能：令全场敌弹进入减速（时间凝滞）。

    与灵击（即时清弹 + 无敌）走不同路线：这里不清弹、也不对 Boss 造成伤害，
    而是把整片弹幕放慢，换取一段从容走位的窗口。
    """
    center = game.player.pos
    game.bullet_slow_timer = config.PLAYER_SKILL_SLOW_DURATION
    game.effects.append(Effect(
        center.x, center.y, game.art.skill_sprites["skill_player"],
        config.BURST_DURATION, start_scale=0.6, end_scale=2.6,
        start_alpha=230, end_alpha=0,
    ))
    game.screen_shake = max(game.screen_shake, config.SKILL_SHAKE)
    game.audio.play("enemy_dead")


def _update_player_skill(game, dt: float) -> None:
    """推进自机技能的状态机：蓄力结束即释放，后摇结束回到就绪。"""
    if game.skill_state == "ready":
        return
    game.skill_timer = max(0.0, game.skill_timer - dt)
    if game.skill_timer > 0.0:
        return
    if game.skill_state == "charge":
        game._release_player_skill()
        game.skill_state = "recover"
        game.skill_timer = config.SKILL_RECOVER_TIME
    else:
        game.skill_state = "ready"


def _decay_screen_shake(game, dt: float, rate: float | None = None) -> None:
    """震屏幅度按固定速率线性衰减到 0。"""
    decay = config.SCREEN_SHAKE_DECAY if rate is None else rate
    game.screen_shake = max(0.0, game.screen_shake - dt * decay)


def _check_collisions(game) -> None:
    """双层判定：擦弹区（外层，不致命）/ 命中区（内层，致命）。

    宽相位：把子弹按格插入空间网格，只对玩家邻域格子内的候选子弹做精确检测，
    避免对所有子弹两两检测。
    精确检测：用线段-圆（扫掠）判定，把子弹一帧位移当作线段，防止高速穿模。
    """
    game.grid.clear()
    max_bullet_reach = 0.0
    for b in game.bullets:
        game.grid.insert(b, b.pos.x, b.pos.y)
        travel = b.pos.distance_to(b.prev_pos)
        max_bullet_reach = max(max_bullet_reach, b.radius + travel)

    px, py = game.player.pos.x, game.player.pos.y
    player_travel = game.player.pos.distance_to(game.player.prev_pos)
    # 将双方本帧位移和实际子弹半径纳入范围，确保扫掠命中的子弹不会被宽相位过滤。
    query_radius = game.player.graze_radius + player_travel + max_bullet_reach
    candidates = game.grid.query(px, py, query_radius)
    game.debug_stats["candidates"] = len(candidates)
    p0x, p0y = game.player.prev_pos.x, game.player.prev_pos.y
    for b in candidates:
        if not b.alive or game.invulnerable_timer > 0.0:
            continue
        game.debug_stats["sweeps"] += 1

        # 转为相对运动：子弹上一帧相对玩家上一帧，至本帧相对位置。
        x1, y1 = b.prev_pos.x - p0x, b.prev_pos.y - p0y
        x2, y2 = b.pos.x - px, b.pos.y - py

        # 先判内层命中区，命中后直接跳过擦弹判定
        if collision.segment_circle(x1, y1, x2, y2, 0.0, 0.0,
                                    game.player.radius + b.radius):
            if not getattr(game, "god_mode", False):
                game.debug_stats["hits"] += 1
                game._on_player_hit(b)
            continue

        # 未命中，再判外层擦弹区（每颗子弹只计一次）
        if not b.grazed and collision.segment_circle(
                x1, y1, x2, y2, 0.0, 0.0,
                game.player.graze_radius + b.radius):
            b.grazed = True
            game.debug_stats["grazes"] += 1
            game.player.graze_count += 1
            game.graze_total += 1
            game.score += config.GRAZE_SCORE
            # 擦弹星环按冷却节流，避免密集弹幕下特效刷屏
            if game.graze_fx_cooldown <= 0.0:
                game.effects.append(Effect(
                    game.player.pos.x, game.player.pos.y,
                    game.art.graze_ring, config.GRAZE_RING_DURATION,
                    start_scale=0.6, end_scale=1.5,
                ))
                game.audio.play("graze")
                game.graze_fx_cooldown = 0.06

    for beam in getattr(game, "boss_beams", ()):
        if (
            game.invulnerable_timer <= 0.0
            and not game.game_over
            and not getattr(game, "god_mode", False)
            and beam.collides_circle(
                game.player.pos.x, game.player.pos.y, game.player.radius
            )
        ):
            game.debug_stats["hits"] += 1
            game._on_player_hit(None)
            break


def _on_player_hit(game, bullet: Bullet | None) -> None:
    if (
        game.invulnerable_timer > 0.0
        or game.game_over
        or getattr(game, "god_mode", False)
    ):
        return

    if bullet is not None:
        bullet.alive = False
    game.hit_total += 1
    game.hit_flash = 0.25
    game.screen_shake = max(game.screen_shake, config.PLAYER_HIT_SHAKE)
    game.audio.play("player_dead")
    # 被击中会让当前符卡失去「取得」资格
    if game.boss is not None and game.boss.alive:
        game.spell_imperilled = True
    game.lives -= 1
    game.bullets.clear()
    game.effects.append(Effect(
        game.player.pos.x, game.player.pos.y, game.art.boss_burst,
        config.BURST_DURATION, start_scale=0.22, end_scale=0.65,
        start_alpha=190, end_alpha=0,
    ))
    game.player.pos = Vector2(config.PLAYER_START_X, config.PLAYER_START_Y)
    game.player.prev_pos = Vector2(game.player.pos)
    game.player.graze_count = 0
    if game.lives <= 0:
        game.lives = 0
        game.game_over = True
        game.invulnerable_timer = 0.0
        game.hit_flash = 0.0
        game.player_shots.clear()
        game.shooting = False
        # 本局到此结束：失败局的新高分同样要写入存档
        game._register_hiscore()
    else:
        game.invulnerable_timer = config.PLAYER_INVULNERABLE_TIME


def _advance_effects(game, dt: float) -> None:
    """推进所有一次性特效，并回收播完的实例。"""
    for effect in game.effects:
        effect.update(dt)
    game.effects = [effect for effect in game.effects if effect.alive]


def _update_fairies(game, dt: float) -> None:
    """推进杂兵并回收出屏者；带弹型的杂兵在场地内按冷却开火。

    妖精的生成时机不再由计时器决定，而是由 :class:`~src.director.StageDirector`
    按关卡波次脚本投放，这里只负责推进与回收，和原作「编队压上」一致。
    """
    fired: list[Bullet] = []
    for fairy in game.fairies:
        fairy.update(dt)
        if (fairy.attack is not None and fairy.alive
                and fairy.state != "leave"
                and fairy.pos.y >= config.PLAYFIELD_TOP
                and fairy.fire_timer <= 0.0):
            fired.extend(spells.emit(
                fairy.attack, game.art, fairy.pos, game.player.pos
            ))
            fairy.fire_timer = fairy.attack.interval
    if fired:
        game.bullets.extend(fired)
    game.fairies = [fairy for fairy in game.fairies if fairy.alive]
