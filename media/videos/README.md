# Videos

## Video A: web UI walkthrough

`demo-a.mp4` is a 113 s screen recording of the Harness web UI (H.264 + AAC, 1440x900, 30 fps).
`demo-a.srt` holds the same captions that are burned into the video.

### What it shows

One run, from question to report:

1. Title card: "Harness: does this prediction support the claim?"
2. New run. The prompt "Is the imatinib pose in ABL1 valid? Boltz-2 and Gnina, 5 seeds" is typed at
   90 ms per character. Quick setup streams its decisions (task, executors, target, ligand, seeds,
   pH, reference, claim) and the Sources panel shows UniProt, RCSB PDB, AlphaFold DB, PDBe-KB,
   PubChem, PDB CCD and ChEMBL.
3. Jobs. The new job's six layer bars start to fill. The KRAS job further down reaches its verdict,
   refused.
4. Job detail. Elapsed time, the layer strip and the log update as checks finish. The log switches to
   the terminal view and back, and the verdict arrives: narrowed.
5. Report. The verdict for the claim "Pose within stated uncertainty", one check row and the
   PoseBusters grid.
6. Ensemble. The structure grid with per-structure values (Mol*), flagged colouring, overlay mode.
7. Agent. An agent's steps stream in: thought, tool call, result, reports, conclusion.
8. Documents. The printable report of the same run.
9. End card: "Every number traceable to a check, a tool and a source."

### Data

Every value on screen is mock data. The UI ran in mock mode (`NEXT_PUBLIC_HARNESS_MODE=mock`, production
build): jobs, records, logs and agent steps come from the in-browser simulator in `web/lib/mock/`
with seed 7, so ids and timings repeat between takes. No harness run, executor or source fetch took
place. The one external file is the 1IEP crystal structure that mock records point Mol* at; the
recording script served a local copy of the RCSB mmCIF to the browser.

The script drives the simulator through `window.__harnessMock`. It pauses it during page changes,
sets its speed so the six layers fill in about 17 s across the Jobs and job pages and the verdict
lands after the terminal view is switched back, restarts agent task `agent_01` at its first step and advances it one step at a time.
Mol* builds its scene through software WebGL in this browser, so two loading waits (2.3 s and 2.7 s)
were cut from the video; 0.8 s of each loading state stays on screen.

### Sound

No each::labs API key was available, so the `sound-effects` skill's API was not used. All sounds
are synthesized from sine partials and filtered noise with numpy and scipy (`video-a/make_sfx.py`): a
soft click, a light tick, a low two-note stop tone, a two-note chime, a short whoosh and a quiet
ambient pad. Each sound sits on an event recorded during the take: a click on every pointer press
(13), a whoosh on every page change (9), a tick for each check result of the new job while its
progress is on screen and for each agent step (40), the stop tone when the KRAS job is refused, and
the chime when the new job's verdict arrives. There is no voice. The pad is at -30 LUFS integrated
and the effects reach -21.3 LUFS momentary at most, with clicks and ticks set a few dB under the
others. The final mix measures -28.0 LUFS integrated with a true peak of -3.9 dBFS.

### Captions

The captions carry the narration. Each one stays on screen for at least the reading hold of the
`human-pace` skill (0.3 s per word, at least 1.5 s). They were edited with the `humanizer` skill,
written to SRT and burned in with ffmpeg and libass, in a 100 px band under the UI on an ink box, so
they never cover UI text.

### Re-recording

The pipeline is in `video-a/`; working files and every take (`v1` to `v15`) are in `out/videos/a/`
(ignored by git). The scripts use absolute paths under `/home/user/harness-hackathon`.

```bash
cd web
NEXT_PUBLIC_HARNESS_MODE=mock NEXT_PUBLIC_MOCK_SEED=7 NEXT_DIST_DIR=.next-video npx next build
NEXT_PUBLIC_HARNESS_MODE=mock NEXT_PUBLIC_MOCK_SEED=7 NEXT_DIST_DIR=.next-video npx next start -p 3301 &
cd ..
mkdir -p out/videos/a/work/assets && cp media/videos/video-a/* out/videos/a/work/
curl -sS -o out/videos/a/work/assets/1IEP.cif https://files.rcsb.org/download/1IEP.cif
.venv/bin/python out/videos/a/work/make_sfx.py out/videos/a 140   # sfx/*.wav
out/videos/a/work/record.sh v16 warm      # playwright-cli run-code take: raw.webm + events.json
.venv/bin/python out/videos/a/work/build.py v16   # captions, cuts, mix, MP4 + WebM, sheets, loudness
out/videos/a/work/publish.sh v16          # copies to out/videos/a/ and media/videos/
```

`record.sh` opens a fresh Chromium (from `/opt/pw-browsers`, 1440x800 viewport, default WebGL) per
take with `cli.config.json`. Captions are in `captions.json`; pacing is in the `PACE` block of
`record.tpl.js`.

## Video B: product film

`demo-b.mp4` is a 120.0 s edited film of the Harness web UI, cut to a 100 BPM music bed composed for it.
`demo-b.srt` holds the same captions as the burned-in band, plus the opening question and the closing line.
Video A is a real-time screen capture; video B rebuilds the product's screens as frame-driven Remotion
components (same layout, tokens and fonts) and films them with a camera, so every frame is a function of time.

| File | Format | Size |
| --- | --- | --- |
| `demo-b.mp4` | 1920x1080, 60 fps, H.264 (yuv420p, BT.709) + AAC 256 kb/s, faststart | 23.5 MB |
| `demo-b.srt` | 17 cues, UTF-8 | 1.5 kB |

### What it shows

| Bars | Time | Scene | Data |
| --- | --- | --- | --- |
| 1-4 | 0:00 | "Does this prediction support the claim?" | none |
| 5-7 | 0:10 | New run: the prompt is typed | the prompt sent to the live interpreter |
| 8-10 | 0:17 | Sources: UniProt, RCSB PDB, AlphaFold DB, PubChem and PDB CCD records with sha256 | real, live lookups |
| 11-13 | 0:24 | Quick setup: request, then eight decisions with their reasons | real, live interpreter |
| 14-15 | 0:31 | Jobs: the run's six layers fill at their recorded speed | run ui-vina |
| 16-19 | 0:36 | Job page: the log reaches the skipped minimisation check and the end of the run | run ui-vina |
| 20-23 | 0:46 | Verdict: incomplete, scoped to "Pose within stated uncertainty" | run ui-vina |
| 24-31 | 0:55 | Report: output support checks with measured value, threshold and origin; PoseBusters 20/20; seed spread | run ui-vina |
| 32-37 | 1:14 | Ensemble: eight cells with PyMOL renders and numbers, then the Mol* overlay of the crystal and five poses | run ui-vina |
| 38-44 | 1:29 | Agent monitor: one task streams its steps | prototype demo data |
| 45-50 | 1:46 | 0.416 Å traced to its check, tools and source file; closing line; logo | run ui-vina |

The run is `ui-vina` from 17 Oct 2026: AutoDock Vina 1.2.7 poses for benzamidine in trypsin (3PTB), five seeds,
outputs supplied to the harness, which ran 39 checks over layers 0 to 5. Its values come from
`web/tests/fixtures/live/ui-record-vina.json` and `log-vina.json`: PoseBusters 20 of 20 on all five poses,
medoid 0.38 Å from the crystal ligand, the five seeds within 0.08 Å of the medoid, redocking control 0.416 Å.
The verdict is incomplete because `l4.minimisation_drift` could not run (no OpenMM environment); the film shows that
verdict and says why. The prompt's settings and the source records were captured from `pah serve` the same day.
The agent task (KRAS and RAF1) is the prototype's mock data, and the film labels it as such. The ensemble's
confidence colouring is disabled for Vina records, which carry no per-residue confidence, so the grid shows per-cell
numbers instead. The job page shows the last fourteen log lines one per beat rather than at recorded speed; the clock
on screen still shows each line's recorded time. A tag in the bottom right of every scene names its data.

### How it was made

The source is in `videos/` (Remotion 4.0.531, React 19.3.1, no Tailwind): `BRAND.md` holds the rules and
`demo-b-prompt.md` the beat sheet. The music is synthesised by `scripts/music.py` (pad chords, a muted pluck
arpeggio, a light kick and hats from bar 5, a sub bass from bar 14, a one-bar drop under the verdict). `scripts/beats.py`
measured 99.999 BPM from the drum stem and the downbeats from the kick stem (grid spread 1.6 ms); every cut lands on a
measured bar. Interface sounds (click, key, tick, chime, whoosh) are synthesised by `scripts/sfx.py` and placed only on
on-screen events. The final render is a 60 fps master with JPEG frames (quality 95), converted to BT.709 and encoded
by `scripts/render.ts --subframes 1 --jpeg` in 50 minutes on the shared 4-core machine; a 120 fps PNG master
with motion blur was started first and stopped because it would have taken well over an hour.

Checks on the delivered file (`scripts/verify.py`, ffmpeg `ebur128`): duration 120.000 s; frame 0 and canvas probes at
50 s and 119.5 s decode to (247, 247, 243) against the canvas token #F7F7F4 (247, 247, 244), limited range, BT.709;
integrated loudness -15.6 LUFS, loudness range 4.9 LU, true peak -1.8 dBFS.

To rebuild:

```bash
cd videos && bun install && bash scripts/setup-assets.sh
python3 scripts/extract-data.py           # values from the run fixtures
bun run audio && bun run beats            # music, sounds, measured grid
REMOTION_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell \
  bun scripts/render.ts DemoB demo-b --duration 120 --poster 114 --subframes 1 --jpeg
bun scripts/srt.ts
```
