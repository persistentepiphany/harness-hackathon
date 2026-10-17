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
