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

## Video A2: walkthrough with a passing introduction

`demo-a2.mp4` is a 106.2 s recording of the same walkthrough as video A (H.264 + AAC, 1440x900,
30 fps, +faststart). `demo-a2.srt` holds its 17 captions, which are also burned in. It was made with
the video A pipeline; the differences are below.

- The UI was built from a clean export of commit e5aa4dc, so the nav reads "Dock Harness". The
  title card, the end card and the agent caption use the same name.
- The first frame already shows the first character of "Does this prediction support the claim?",
  which types itself at 40 ms per character under the Dock Harness mark and then stays up for its
  1.8 s reading hold. Video A opened on a static title card held for 2.8 s.
- The prompt is typed with one `pressSequentially` call at 39 ms per character (video A: 90 ms),
  and the cursor reaches the prompt 1 s after the title card instead of 2 s.
- Nothing fails in the introduction. The KRAS · RAF1 preset job, which ends refused, is taken out
  of the simulator before the take, so the Jobs page lists the new run, the narrowed ABL1 imatinib
  pose run and the ABL1 series ranking run. The followed run ends narrowed (36 pass, 4 warn,
  0 stop). The run leaves the queue while its page is open, so that page does not sit on "Waiting
  for a slot".
- The app is loaded with `?latency=0`, the fade-in of pages, job cards and replayed log lines is
  turned off, and the one-frame loading placeholders ("loading job", log "connecting") are cut from
  the picture.
- The sound has no background bed and no check-result or agent-step ticks. It has a click on each
  pointer press (13), one key sound per typed character (101: 39 in the title, 62 in the prompt,
  six synthesized variants), a whoosh on each page or scene change (9, at most one per 0.6 s) and a
  chime when the verdict arrives. There is no stop tone. The mix measures -28.9 LUFS integrated,
  -24.9 LUFS momentary maximum and -7.9 dBFS true peak.
- The rewound agent task notifies the page, so the Agent page opens on the running task and not on
  its earlier completed state.

The report, ensemble, agent and documents scenes are otherwise as in video A; the agent's own steps
still report refused poses. Every value on screen is mock data from the simulator with seed 7.

The changed scripts are in `video-a2/` (`timeline.py` is the one in `video-a/`). Final take: `v5`.

```bash
mkdir -p out/videos/a2/src out/videos/a2/work/assets
git archive e5aa4dc web | tar -x -C out/videos/a2/src
cp -al web/node_modules out/videos/a2/src/web/node_modules
cd out/videos/a2/src/web
NEXT_PUBLIC_HARNESS_MODE=mock NEXT_PUBLIC_MOCK_SEED=7 NEXT_DIST_DIR=.next-video2 npx next build
NEXT_PUBLIC_HARNESS_MODE=mock NEXT_PUBLIC_MOCK_SEED=7 NEXT_DIST_DIR=.next-video2 npx next start -p 3302 &
cd /home/user/harness-hackathon
cp media/videos/video-a2/* media/videos/video-a/timeline.py out/videos/a2/work/
curl -sS -o out/videos/a2/work/assets/1IEP.cif https://files.rcsb.org/download/1IEP.cif
.venv/bin/python out/videos/a2/work/make_sfx.py out/videos/a2   # sfx/*.wav, keys included
out/videos/a2/work/record.sh v6 warm press   # third argument: press or page (in-page typing loop)
.venv/bin/python out/videos/a2/work/build.py v6   # add --webm for a WebM copy
out/videos/a2/work/publish.sh v6
```

## Video C: the leading result, the problem and the harness

`demo-c.mp4` is a 157.3 s edited film (1920x1080, 30 fps, H.264 + AAC 192 kb/s, +faststart) built from
HTML scene stills, PyMOL renders and three takes of the live web UI. `demo-c-nosfx.mp4` is the same
edit and the same music without the interface sounds. `demo-c.srt` holds the captions that are burned
into both files. A section number and title sit on each scene, and every scene that shows a number
carries a source tag in the bottom right.

### What it shows

| Time | Scene | Data |
| --- | --- | --- |
| 0:00 | 12 perturbed Boltz-2 predictions (CDK2 1B38, FtsE 8X61, MEK1 7XLP, glucose dehydrogenase 2VWH; 3 runs each) in a 4x3 grid of PyMOL renders, each with ipTM and pocket pLDDT, first marked "Without the harness: called valid", then "With the fact file: rejected" with that structure's contacts recovered, buried unsatisfied polar atoms, PoseBusters result or torsion strain | `bench/runs/*`, images and values in `media/figures/twelve/` |
| 0:22 | 1 The problem: three citation cards (PoseBusters, the Mac1 prospective co-folding study, Runs N' Poses) | `video-c/REFERENCES.md` |
| 0:37 | 2 The old way: CDK2 and ATP into Boltz-2, the raw `confidence_*.json` beside the structure, then what the score hides (13 residues cut to glycine, 1 of 9 crystal contacts, 4 buried polar atoms unpaired) | bench run 3 |
| 0:47 | 3 With the harness: what a model gives (pLDDT, ipTM, maybe a docking score) beside the harness checks grouped by layer with the tool that measures each; then the harness verdict for the same CDK2 input (stop) and its issues | `README.md` check tables; bench run 3 `record.json` |
| 1:07 | Models it runs and checks, with A100 or CPU | `README.md` Tools used |
| 1:15 | 4 Input and output: a new run picked from the menus in the live UI (Trypsin, benzamidine, Boltz-2, Chai-1, DiffDock-L, AutoDock Vina, 5 seeds; Start run is not pressed); the finished run `ligand_pose-249098d10007` beside its request and the 3PTB crystal (verdict, issues, Boltz-2 medoid), execution rows with A100 timings and the Ensemble; a scroll through one expanded check, the artifact list and the thresholds with their origin | live UI |
| 2:06 | Agents: the live Agent view with an agent's steps | live UI |
| 2:12 | 5 The AI agent result: GLM-4.6, temperature 0, 3 repeats; run 3 balanced accuracy 0.50 vs 0.75 (95% CI 0.50 to 1.0, McNemar p 0.125); 12 of 12 vs 0 of 12 perturbed Boltz-2 poses rejected; the agent with the fact file also rejected 3 of 6 valid poses | `bench/runs/2026-10-17T1859Z-849c856/results/stats.json` |
| 2:24 | Files every run writes: report.html, provenance graph, PyMOL renders, figures | bench run 3, run ui-vina |
| 2:31 | "Every number traceable to a check, a tool and a source.", the site URL and a references line | |

### Sources and checks

The three studies were checked against Europe PMC records on 2026-10-18; `video-c/REFERENCES.md`
lists each citation, what it supports and what was verified. The specification's "489 complexes",
"about 75 ROC AUC" and "53.8 ROC AUC" figures could not be traced to an opened source version and are
not in the film; the film shows the verified values from version 2 of the Mac1 study (557 ligands,
AUC 0.76 and 0.73) instead.

The 12 renders were made for this film by `video-c/render_twelve.py` from the medoid pose named in
each run's harness record. The live UI takes were recorded on 2026-10-18 against
https://persistentepiphany--pah-web.us-east.modal.run with a CDP screencast (1280x627 CSS px at 1.5x);
the report, ensemble and agent element shots were taken the same day at 2x by `video-c/shoot_live.js`.

### Sound

Music is the v1 sequence (`build.py`, numpy: pad chords in D major at 100 BPM, sub bass, light kick,
off-beat hats, sparse pluck) with the music bus 2 dB lower than v1. Interface sounds come from
`video-c/make_sfx.py` (synthesised, no API): a soft click on each recorded pointer press (10), a soft
whoosh at each scene change (14) and a tick on the reveal in "The old way". No text is typed in this
film, so there are no key ticks.

### Rebuild

```bash
uv pip install --python .venv/bin/python pymol-open-source-whl pillow scipy
W=/home/user/harness-hackathon/out/videos/c
.venv/bin/python media/videos/video-c/render_twelve.py          # media/figures/twelve/*
node media/videos/video-c/shoot_live.js $W/live                 # live UI element shots
.venv/bin/python media/videos/video-c/render_3ptb.py                # $W/live/3ptb_pocket.png
for t in input evidence agent; do node media/videos/video-c/record3.js $W/r3_$t $t; done
node media/videos/video-c/shoot.js $W prep                      # report.html and graph.svg stills
.venv/bin/python media/videos/video-c/scenes.py $W              # html/*.html, shots.json
node media/videos/video-c/shoot.js $W scenes                    # stills/*.png
.venv/bin/python media/videos/video-c/build.py $W v9            # both MP4s, SRT, contact sheet
```

Final take: `out/videos/c/v9`. `record.js` and `record2.js` are the takes of the first version and are
kept for reference; the first version pressed Start run, which this version does not.
