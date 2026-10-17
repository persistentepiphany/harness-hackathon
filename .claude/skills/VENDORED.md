# Vendored skills

Copied from upstream on 2026-10-17. Each folder keeps its upstream license. To update one, copy the new upstream files over it, then re-apply the local patches listed below.

| Skill | Upstream | Commit | License |
|---|---|---|---|
| `sound-effects` | [awesome-genmedia/skills](https://github.com/awesome-genmedia/skills/tree/main/sound-effects) | `e4e641e` | MIT |
| `presentation-skill` | [siril9/presentation-skill](https://github.com/siril9/presentation-skill) v0.14.0 | `efd899c` | MIT |
| `product-film` | [Rieranthony/product-film-skill](https://github.com/Rieranthony/product-film-skill) v1.1.0 | `fe11efc` | MIT |
| `humanizer` | [blader/humanizer](https://github.com/blader/humanizer) v3.1.0 | `8c307f3` | MIT |
| `playwright-cli` | [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) 0.1.22 | `b85c7a7` | Apache-2.0 |

`human-pace` is ours.

## What was copied

- `presentation-skill`: the files upstream publishes to npm (`package.json` `files`), plus `package-lock.json`. Example decks, tests and the plugin snapshot were left out.
- `product-film`: `plugins/product-film/skills/product-film/`.
- The others: the skill folder or `SKILL.md` as is.

## Local patches

- `product-film/templates/kit/cursor.tsx`: cursor glide cap raised from 0.46 s to 0.8 s (`GLIDE_MAX`) for human pace.
- `product-film/scripts/render.ts`: `--concurrency` capped at the CPU count. Upstream hardcodes 8, and Remotion refuses that on a machine with fewer cores.
- `product-film/scripts/render.ts` and `stills.ts`: use `REMOTION_BROWSER_EXECUTABLE` when it is set. Cloud sessions can't download Remotion's Chrome, so the setup hook points it at the preinstalled one. When the variable is unset, nothing changes.
