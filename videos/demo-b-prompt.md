<context>
Harness (the Prediction Assurance Harness) decides whether a co-folding or docking result can support a declared
claim, layer by layer, and records where every number comes from. This film plays as a demo video with sound for a
hackathon jury and scientists. Read `videos/BRAND.md` first; this prompt only adds the story.
</context>

<inputs>
Decided: 1920x1080, 60 fps, light, 50 bars at 100 BPM, 120 s. Music: composed by `scripts/music.py`, measured by
`scripts/beats.py` (tempo 99.999 BPM from the drum stem; phase and downbeat from the kick stem; grid spread 1.6 ms).
Film bar 1 opens at frame 0; beats.json bar 0 is film bar 2.
</inputs>

<direction>
Calm, exact, readable. The product does the talking; captions say what the picture shows and nothing more.
Ingredients: product UI only · captions in a band · cuts and camera moves on bars · the user's cursor for clicks ·
the logo mark at the end. Banned: glows, particles, bouncy easing, invented surfaces, any number not in a record.
</direction>

<structure>
100 BPM, 4/4, 50 bars, one beat 0.6 s.

Bars 1-4, cold open. "Does this prediction support the claim?" lands word by word, then "Harness checks co-folding
and docking results, layer by layer." Pad and pluck only.
Bars 5-7, New run. The cursor clicks the prompt box, the prompt types at about 11 characters a second. Kick and hats
enter on bar 5.
Bars 8-10, Sources. The camera moves to the Sources panel; UniProt, RCSB PDB, AlphaFold DB, PubChem and PDB CCD
records resolve one per two beats, each with its sha256.
Bars 11-13, Quick setup. Click; the request row, then eight decisions, one per beat, each with its reason. Start run.
Bars 14-15, Jobs. The new card replays run ui-vina at its recorded speed: provenance, integrity, adequacy,
applicability fill; output validity is running at the cut. Bass enters.
Bars 16-19, Job page. The log shows the remaining lines one per beat, the clock showing recorded times; the camera
pushes in on the skipped minimisation check, then pulls back as output support finishes.
Bars 20-23, Verdict. Drums drop for a bar; "Incomplete" lands with the claim, then the verdict statement.
Bars 24-31, Report. Output support checks with measured value and threshold; thresholds with their origin and the
ranking-only Vina score; PoseBusters 20 of 20; seed spread with the five seeds inside 0.08 Å of the medoid.
Bars 32-37, Ensemble. Eight cells with PyMOL renders and their numbers; click overlay; the Mol* overlay of the
crystal and the five mode-0 poses, slow push to the ligands.
Bars 38-44, Agent. The prototype's demo task streams one step per two beats; tag: prototype demo data.
Bars 45-50, close. 0.416 Å traced to l5.controls.redocking, spyrmsd 0.9.0 and the RCSB file with its sha256; the
closing line; the logo mark draws and the wordmark lands. Drums and bass out, pad rings out.
</structure>

<gotchas>
The run's verdict is incomplete (l4.minimisation_drift could not run: no OpenMM environment); the film says so and
never shows another outcome. Vina outputs were supplied to the harness, not executed by it; the tag says so. The
ensemble's confidence colouring is disabled for Vina records, so the film shows per-cell numbers, not pLDDT.
</gotchas>
