# Visual styles

AI films come in very different formats: realistic live action, claymation, pixel art, paper cutout,
stylized 3D, anime. The style is chosen first (`/ai-film-pipeline:film-new` asks), and it then drives
**every** stage. Packs live in `styles/<id>.json`, and choosing one freezes a copy into
`films/<film>/00_brief/style.json`, so improving a pack later never changes a film mid-production.

| Style | id | Motion | Post in the master | Grain |
|---|---|---|---|---|
| Realistic cinematic | `realistic-cinematic` | real-time 24 fps | black-point crush | fine |
| Claymation | `claymation` | stop-motion on twos (12 fps) | frame stepping | light |
| Pixel art | `pixel-art` | stepped sprites (12 fps) | 480x270 pixel grid, 48-colour Bayer-dithered palette | none |
| Paper cutout | `paper-cutout` | on twos, split-pin limbs | frame stepping, paper texture multiply | light |
| Stylized 3D | `stylized-3d` | smooth 24 fps, squash and stretch | none | none |
| Anime | `anime` | limited animation on twos | frame stepping | none |

## What a pack controls
| Field | Used by | Effect |
|---|---|---|
| `look` | every image and video prompt (verbatim) | the visual language |
| `character_medium`, `sheet_backdrop`, `plate_medium`, `vehicle_medium` | `fp sheet-prompts`, `fp plate-prompts` | what a character, set or vehicle IS in this medium |
| `motion` | video FORMAT section | how things move (on twos, sprite steps, real time) |
| `constraints` | video CONSTRAINTS section (lint-checked) | what breaks the style |
| `camera_language`, `lighting_menu` | scene designer, prompt writer | per-shot `lens` and `lighting` choices |
| `post` | `fp master` | `frame_step`, `pixelate` [w,h], `palette` (colours), `texture` ("paper") |
| `grade` | `10_finish/grade.json` defaults | halation, eq (contrast, saturation, gamma), black point, bloom, grain |
| `target_metrics` | `fp lookmatch`, `fp verify --final` | luma, black/white point, saturation, contrast to aim for |
| `pacing` | `fp scenes` warnings, editor | setups per minute, median shot, montage hit, dialogue share, title time |
| `critic` | continuity-critic | style-break checks applied to every image and take |

## Custom styles
Copy `styles/_template.json`, fill in every field (watercolour, rotoscope, noir, toy-brick-free miniatures,
claymation-with-felt...), then run `fp style <film> --custom my_style.json`. If a custom style proves
itself on a real film, add it to `styles/` in the repo so everyone gets it.

## Tuning a style
After a film, run `fp lookmatch <film>` and compare against the pack's `target_metrics`. If good films in a
style consistently land somewhere else, update the pack's targets and grade defaults, then bump the plugin
version.
