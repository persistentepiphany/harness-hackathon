# Harness video kit

The look, rules, assets and code for Harness films. Each film prompt points here and only adds its story.
Sources: `web/app/globals.css`, `web/design/prototype/HANDOFF.md` §3, `web/components/`, `docs/UI.md`,
`CLAUDE.md`, and the coordinator's brief for film B. When this file and the repo disagree, the repo wins.

## The brief (decided by the coordinator, no interview)
- Plays: demo video with sound, for a hackathon jury and scientists. Format 16:9, 1920x1080, 60 fps. Length 120 s.
- Music: composed in code for the film (`scripts/music.py`), 100 BPM, no licence needed.
- Must show: New run (prompt, quick setup, sources), the job (six layers, log, verdict), report highlights
  (check row with threshold and origin, PoseBusters, seed spread), ensemble grid and overlay, agent monitor.
- Ingredients: product UI only, logo mark at the end · short captions in a band · cuts and camera moves on bars ·
  the user's cursor for real clicks.
- Ending: "Every number traceable to a check, a tool and a source." then the logo mark and wordmark.

## Hard rules
- Surfaces: canvas `#F7F7F4` everywhere; `#FFFFFF` with a 1 px `#E6E6E1` border only where the product draws a
  card (prompt box, log panel, structure cells, task cards). Source: HANDOFF §3 "no card chrome except tabular".
- No glows, particles, shadows, gradients or bouncy easing. Motion is the product's: fadeUp 0.3 s ease-out, spin
  0.8 s, pulse 1.2 s (`globals.css`), plus camera moves on a heavy spring.
- Numbers in Geist Mono with a thin space before the unit; missing values are an en dash (`docs/UI.md`).
- Copy (captions, titles): plain and factual, no em dashes, no staged contrasts (humanizer skill, `CLAUDE.md`).
  The product's own UI strings are kept as they are, including the decision rows' ` — ` separator.
- Claims: only what a record shows. Every scene says where its data comes from in the bottom-right tag.

## Frame
- Top: the product nav at 1.5x (66 px). Picture: y 66 to 940, the page filmed at 1.5x to 2.6x so 13 px UI text
  reads at 20 px and up. Caption band: y 940 to 1080 under a hairline, caption 34 px Geist 500 ink, tag 18 px
  Geist Mono muted.
- Titles (cold open, closing line): Geist 600, 104 to 118 px, ink, one accent word.

## Color (hex, from `web/app/globals.css`)
| Token | Value | Use |
|---|---|---|
| canvas | #F7F7F4 | background |
| surface | #FFFFFF | cards only |
| line / line2 | #E6E6E1 / #EFEFEB | borders, row rules |
| ink / ink2 | #1A1A18 / #55554F | text |
| muted / faint | #8B8B85 / #B9B9B3 | labels, missing values |
| accent / accent-deep | #B07E2C / #8E6420 | focus, running, ranking scores |
| pass / warn / stop | #3B8A58 / #C28A1A / #C4513B | results |
| docking / seed | #5B7FA6 / #C9A86A | tool calls, seed poses |

## Type
- Geist and Geist Mono variable fonts from the `geist` package (1.8.1), copied to `public/fonts` by
  `scripts/setup-assets.sh` and loaded with `@remotion/fonts`.

## Signature elements
| Element | Look | Source | In film B |
|---|---|---|---|
| Status dot | 6 to 8 px round, result colour; square for tool steps | `ui/StatusDot.tsx` | twin |
| Ring | line ring, accent top, spin 0.8 s | `run/parts.tsx RingDot`, `ui/Spinner.tsx` | twin, driven by t |
| Layer progress | six 3 px segments, worst result colour | `jobs/LayerProgress.tsx` | twin |
| Buttons | 6 px radius, ink fill or 1 px outline | `ui/Button.tsx` | twin, keeps its width |
| Logo mark | rounded square outline, accent inner square | `app/icon.svg`, `nav/TopNav.tsx` | draws itself at the end |

## Components
| Need | Component | In films |
|---|---|---|
| Nav | `nav/TopNav.tsx` | twin (data hooks, Next links) |
| Prompt, decisions, sources | `run/PromptBox`, `run/DecisionStream`, `run/SourcesPanel` | twins (state, timers) |
| Job card, strip, log | `jobs/JobCard`, `jobs/LayerStrip`, `jobs/LogPanel` | twins (hooks, scroll effects) |
| Verdict, checks, PoseBusters, seed spread | `report/VerdictHeader`, `CheckTable`, `PoseBustersGrid`, `figures/SeedSpread` | twins |
| Ensemble grid | `ensemble/StructureGrid` | twin with the run's PyMOL PNGs |
| Overlay | `ensemble/OverlayView` (Mol*) | screenshot of the running app (WebGL on its own clock) |
| Agent monitor | `agent/TaskList`, `TaskDetail`, `StepTimeline` | twins |

No component is imported from `web/`: they are styled with Tailwind classes, and this workspace never resolves the
web app's Tailwind. Twins copy the classes as inline styles.

## Claims
- Shows: a real run (`ui-vina`, AutoDock Vina 1.2.7 outputs supplied to the harness, 3PTB, 5 seeds) and its record;
  the live interpreter and source lookups for the typed prompt; the prototype's demo agent task, labelled.
- Never shows: per-residue confidence colouring for this run (Vina has none; the product disables it), a verdict
  other than the recorded one (incomplete), or any number the records do not hold.

## Workspace
- `videos/`, Remotion 4.0.531 (all `@remotion/*` pinned to it), React 19.3.1, no Tailwind.
- Scripts: `extract-data.py`, `music.py`, `sfx.py`, `beats.py`, `stills.ts`, `render.ts`, `verify.py`, `srt.ts`.
