---
name: human-pace
description: Pacing defaults for anything a person watches or listens to, such as demo recordings, product films, screen captures, slide decks, voiceover and sound effects. Use alongside playwright-cli, product-film, presentation-skill and sound-effects whenever you record, render, time or narrate something, so it plays at a normal human pace and not machine speed.
---

# Human pace

A viewer should be able to follow every step without pausing the video. If they need to scrub back, it is too fast. If they wait for anything to happen, it is too slow.

## Defaults

| Thing | Pace |
|---|---|
| Cursor travel | 0.8–0.9 s per move, on a slight curve |
| After a click | 0.8 s before the next move, so the UI can react |
| Typing | 90 ms per character (about 11 a second), one call per string |
| Reading hold | max(1.5 s, 0.3 s per word) for any new text the viewer must read |
| Scrolling | one smooth scroll, then 1.2 s to look. Never jump, never crawl |
| Page load | wait for network idle, then 1.5 s before the first action |
| Chapter or title card | 2.5 s |
| End of recording | hold the final state 2 s |
| Voiceover | 140–160 words per minute, with a short breath between sentences |
| Slides | 30–90 s each when presented. Auto-advance never under 6 s or the reading hold |
| Sound effects | only on real events (click, send, success). UI sounds 18–24 dB under the voice |

Keep one idea per scene or slide. If a step needs explaining, slow it down or cut it. Don't speed it up.

## Playwright recordings (`playwright-cli`)

- `.playwright/cli.config.json` adds `slowMo: 150` and a 1280x800 viewport to every session.
- For a video, start from [hero-template.js](hero-template.js) and run it with `npx playwright-cli run-code --filename <copy>.js`. Its `PACE` block holds the numbers above.
- `screencast.showActions` paces every action by its `duration`, so type a whole string with `pressSequentially(text, { delay: 90 })`. Typing key by key, or scrolling with many wheel ticks, multiplies that delay and drags.
- Check the result: `ffprobe` the duration, then look at a 1 fps contact sheet (`ffmpeg -i demo.webm -vf "fps=1,scale=480:-1,tile=5x3" -frames:v 1 sheet.png`).

## Product films (`product-film`)

The upstream skill is tuned for fast showreels. For demos and walkthroughs:

- Plan at 90–110 BPM, not 150. Use a faster tempo only for a teaser the user asked for.
- Hold each punchline card for the reading hold after its last word lands.
- A feature scene gets 3–4 bars. Never put more than one new idea in 2 bars.
- The kit's cursor glide is set to 0.8 s (`GLIDE_MAX` in `templates/kit/cursor.tsx`).
- Typed text on screen: 8–12 characters a second.

## Decks (`presentation-skill`)

- At most about 30 words of body text per slide. Put the rest in speaker notes.
- Speaker notes should read aloud at 140–160 wpm in the time the slide gets.

## Writing

Any text the viewer reads or hears (captions, punchlines, slide copy, narration) is short. Write it, then run the `humanizer` skill on it before it goes into a build.
