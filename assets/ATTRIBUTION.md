# Gameplay Asset Credits

The gameplay artwork listed here was copied from the user-provided
`东方Project游戏开源素材库/TH06 东方红魔乡` asset package. Images are organized
under `character/`, `bullet/`, `effect/`, and `scene/`. Sprite sheets are shipped
as a colour image plus a greyscale mask (`_a.png`); the mask's red channel
becomes the alpha channel at load time.

These assets remain the property of their respective rights holders and are
not covered by this repository's MIT License, which applies to code only.

Images (`CM_DAT` = character/bullet data, `ST_DAT` = stage data,
`ED_DAT` = ending data, `TL_DAT` = title/menu data):

- `scarlet-mansion.jpg`: `TL_DAT/select00.jpg`
- `player-sheet.png` / `player-mask.png`: `CM_DAT/player00.png` / `player00_a.png`
  (10 frames: 4 upright, 3 leaning left, 3 leaning right)
- `bullet-a-sheet.png` / `bullet-a-mask.png`: `CM_DAT/etama3.png` / `etama3_a.png`
  (8 large orb colours + rice bullets)
- `bullet-b-sheet.png` / `bullet-b-mask.png`: `CM_DAT/etama4.png` / `etama4_a.png`
  (small orbs, medium orbs, bursts)
- `effect-sheet.png`: `CM_DAT/eff00.png` (already alpha-encoded)
- `skill-player.png`: cropped from `CM_DAT/eff00.png` (hollow ring motif,
  upscaled) — player special-skill charge/release aura
- `skill-boss.png`: cropped from `CM_DAT/eff00.png` (soft glow orb, upscaled)
  — Boss special-skill charge aura
- `stage-bg.png` / `stage-bg-mask.png`: `ST_DAT/stg4bg.png` / `stg4bg_a.png`
  (kept for the older single-stage layout)
- `fairy-sheet.png` / `fairy-mask.png`: `ST_DAT/stg1enm.png` / `stg1enm_a.png`
- `fairy-variant-sheet.png` / `fairy-variant-mask.png`:
  `ST_DAT/stg1enm2.png` / `stg1enm2_a.png` (alternate fairy sprite animation)
- `boss-face-a.png` / `boss-face-a-mask.png`: `ST_DAT/face12a.png` / `face12a_a.png`
- `boss-face-b.png` / `boss-face-b-mask.png`: `ST_DAT/face12c.png` / `face12c_a.png`
- `boss-face-c.png` / `boss-face-c-mask.png`: `ST_DAT/face10a.png` / `face10a_a.png`
- `ending-victory.jpg`: `ED_DAT/end03.jpg`
- `ending-defeat.jpg`: `ED_DAT/end00.jpg`
- `ending-afterword.jpg`: `ED_DAT/end01.jpg` (original ending-scene illustration)
- `ending-credits.jpg`: `ED_DAT/staff00.jpg` (original staff-roll background)
- `ending-roll-1.jpg` ~ `ending-roll-10.jpg`: `ED_DAT/end02.jpg`, `end05.jpg`,
  `end06.jpg`, `end08.jpg`, `end10.jpg`, `end12.jpg`, `end04.jpg`, `end07.jpg`,
  `end09.jpg`, `end11.jpg` (original ending illustrations, cycled behind the
  scrolling staff roll)
- `result-screen.jpg`: `TL_DAT/result.jpg` (original score/result screen artwork)

## Three-stage expansion

Per-stage scrolling backdrops (`ST_DAT`, three of the seven stage backgrounds):

- `stage1-bg.png` / `-mask.png`: `ST_DAT/stg1bg.png` / `stg1bg_a.png`
- `stage2-bg.png` / `-mask.png`: `ST_DAT/stg3bg.png` / `stg3bg_a.png`
- `stage3-bg.png` / `-mask.png`: `ST_DAT/stg5bg.png` / `stg5bg_a.png`

Per-stage fairy sheets, small (`smallN`) and large (`largeN`) variants:

- `enemy1-sheet.png` / `-mask.png`: `ST_DAT/stg1enm.png` / `stg1enm_a.png`
- `enemy1b-sheet.png` / `-mask.png`: `ST_DAT/stg1enm2.png` / `stg1enm2_a.png`
- `enemy2-sheet.png` / `-mask.png`: `ST_DAT/stg2enm.png` / `stg2enm_a.png`
- `enemy2b-sheet.png` / `-mask.png`: `ST_DAT/stg2enm2.png` / `stg2enm2_a.png`
- `enemy3-sheet.png` / `-mask.png`: `ST_DAT/stg6enm.png` / `stg6enm_a.png`
- `enemy3b-sheet.png` / `-mask.png`: `ST_DAT/stg5enm2.png` / `stg5enm2_a.png`

Dialogue and HUD character portraits (`ST_DAT` for enemies, `CM_DAT` for the
player character):

- `portrait-reimu-1/2/3`: `CM_DAT/face00a.png`, `face00b.png`, `face00c.png`
  (the same `face00a.png` is also used, via `portrait-reimu-1.png`, as the
  application icon: `assets/icon.png` for the window icon at runtime and
  `icon.ico` for the packaged executable)
- `portrait-rumia-1/2`: `ST_DAT/face03a.png`, `face03b.png`
- `portrait-cirno-1`: `ST_DAT/face05a.png`
- `portrait-meiling-1/2`: `ST_DAT/face06a.png`, `face06b.png`
- `portrait-patchouli-1/2`: `ST_DAT/face08a.png`, `face08b.png`
- `portrait-sakuya-1/2`: `ST_DAT/face09a.png`, `face09b.png`
- `portrait-remilia-1`: `ST_DAT/face10a.png`

(The `_a` mask of each portrait follows the same source name, e.g.
`portrait-rumia-1-mask.png` is `ST_DAT/face03a_a.png`.)

Sound effects live in `audio/` and come from `IN_DAT` (see
`audio/ATTRIBUTION.md`). Original Touhou Project artwork and audio are copyright
© ZUN. The user confirmed that the provided material is licensed for use in this
project.
Frames are extracted with the `_a.png` masks at runtime; source art is otherwise
kept unchanged.
