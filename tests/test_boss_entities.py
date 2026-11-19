import unittest

from src import config, spells
from src.entities import Boss, BossBeam, PlayerShot


class BossEntityTests(unittest.TestCase):
    def test_boss_bounces_at_horizontal_bounds(self) -> None:
        boss = Boss(config.BOSS_RIGHT_BOUND - 1, config.BOSS_START_Y)
        boss.direction = 1

        boss.update(0.1)

        self.assertEqual(boss.pos.x, config.BOSS_RIGHT_BOUND)
        self.assertEqual(boss.direction, -1)

    def test_boss_changes_phase_at_half_health_and_health_is_clamped(self) -> None:
        boss = Boss(config.BOSS_START_X, config.BOSS_START_Y)

        boss.take_damage(boss.max_hp / 2)
        self.assertEqual(boss.phase, 2)

        boss.take_damage(boss.max_hp)
        self.assertEqual(boss.hp, 0)
        self.assertFalse(boss.alive)

    def test_boss_phase_hp_uses_unequal_spell_thresholds(self) -> None:
        boss = Boss(
            config.BOSS_START_X, config.BOSS_START_Y,
            spec=spells.STAGE_BOSS_SPECS["rumia"],
        )
        phase_hps = [spell.hp for spell in boss.spec.spells]
        later_phases_hp = sum(phase_hps[1:])

        boss.hp = later_phases_hp + 1.0
        self.assertEqual(boss.phase, 1)
        self.assertEqual(boss.phase_hp, 1.0)
        self.assertEqual(boss.phase_max_hp, phase_hps[0])

        boss.hp = later_phases_hp
        self.assertEqual(boss.phase, 2)
        self.assertEqual(boss.phase_hp, phase_hps[1])
        self.assertEqual(boss.phase_max_hp, phase_hps[1])

    def test_stage_boss_phase_hp_increases_each_phase(self) -> None:
        expected = {
            "rumia": [650.0, 850.0, 1100.0],
            "cirno": [650.0, 900.0, 1150.0],
            "remilia": [1000.0, 1200.0, 1400.0, 1600.0, 1800.0],
        }
        for key, spec in spells.STAGE_BOSS_SPECS.items():
            phase_hps = [spell.hp for spell in spec.spells]
            self.assertEqual(phase_hps, expected[key])
            self.assertTrue(
                all(later > earlier
                    for earlier, later in zip(phase_hps, phase_hps[1:])),
                msg=f"{spec.key} HP should increase across phases",
            )
        fallback_hp = [
            spell.hp for spell in spells.DEFAULT_BOSS_SPEC.spells
        ]
        self.assertEqual(fallback_hp, expected["rumia"])
        self.assertEqual(config.MIDBOSS_HP, 650.0)

    def test_boss_beam_warns_hits_and_expires(self) -> None:
        beam = BossBeam(
            100.0, 100.0, 0.0, 300.0, 38.0, 0.5, 1.0,
            (255, 170, 55),
        )

        self.assertFalse(beam.active)
        self.assertFalse(beam.collides_circle(200.0, 100.0, 5.0))
        beam.update(0.5)
        self.assertTrue(beam.active)
        self.assertTrue(beam.collides_circle(200.0, 110.0, 5.0))
        self.assertFalse(beam.collides_circle(200.0, 150.0, 5.0))
        beam.update(1.0)
        self.assertFalse(beam.alive)

    def test_patchouli_special_has_a_telegraphed_laser(self) -> None:
        beams = spells.MIDBOSS_SPECS["patchouli"].special.beams

        self.assertEqual(len(beams), 2)
        self.assertEqual(beams[0].telegraph, 0.75)
        self.assertGreaterEqual(beams[0].width, 30.0)

    def test_player_shot_moves_up_and_records_previous_position(self) -> None:
        shot = PlayerShot(100, 100)

        shot.update(0.1)

        self.assertEqual(shot.prev_pos.y, 100)
        self.assertLess(shot.pos.y, 100)

    def test_player_shot_is_removed_above_screen(self) -> None:
        shot = PlayerShot(100, 0)

        shot.update(0.1)

        self.assertFalse(shot.alive)


if __name__ == "__main__":
    unittest.main()
