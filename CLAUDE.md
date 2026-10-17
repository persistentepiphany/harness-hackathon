# Harness hackathon

This repo holds the skills we use to make demos, videos and presentations. They live in `.claude/skills/`. Where each one came from is in `.claude/skills/VENDORED.md`.

| Need | Skill |
|---|---|
| Record a browser demo or drive a web app | `playwright-cli` |
| Product film, launch video or promo in Remotion | `product-film` |
| Editable `.pptx` deck | `presentation-skill` |
| Sound effects | `sound-effects` (needs `EACHLABS_API_KEY`) |
| Pacing for anything people watch | `human-pace` |
| Edit prose so it doesn't read as AI | `humanizer` |

## House rules

- **Human pace.** Load `human-pace` with any skill that records, renders or times something. Use its numbers unless the user asks for something else.
- **Short writing.** Captions, slide copy, narration, READMEs and PR text say what they need to and stop. Run `humanizer` on the draft before it ships.
- Put rendered output in `out/`, which git ignores.

## Setup

The SessionStart hook runs `scripts/setup-skills.sh`. To run it yourself, use `npm run setup`. Use `npm run check:skills` to check the skills.
