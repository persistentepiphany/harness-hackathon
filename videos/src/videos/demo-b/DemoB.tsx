// Film B: "Does this prediction support the claim?" A 120 s product film of the Harness web UI,
// cut to a 100 BPM bed composed for it (scripts/music.py). Every frame is a function of time.

import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from 'remotion';

import { TargetLog } from '../../kit/debug';
import { useTime } from '../../kit/time';
import { Agent } from './acts/Agent';
import { Close } from './acts/Close';
import { ColdOpen } from './acts/ColdOpen';
import { Ensemble } from './acts/Ensemble';
import { JobCard } from './acts/JobCard';
import { JobLog } from './acts/JobLog';
import { NewRun } from './acts/NewRun';
import { Report } from './acts/Report';
import { Verdict } from './acts/Verdict';
import { B, CAPTIONS, DURATION, scene, sfxEvents, sfxPeak, TAGS } from './cues';
import { loadProductFonts } from './fonts';
import { layerEndAt, runEndAt } from './runtime';
import { BandRule, Captions, Tag, TopNav, type NavState } from './ui/chrome';
import { C } from './tokens';

loadProductFonts();

export const DEMO_B_SECONDS = DURATION;
export type DemoBProps = { fps: number; debug: boolean };

function navAt(t: number): NavState {
  const live = { badges: { report: 12, docs: 12 }, status: 'idle', running: false, mode: 'live' };
  if (t < scene('jobCard').from) return { active: 'new', ...live };
  if (t < scene('verdict').from) {
    const running = t < runEndAt;
    return running
      ? { active: 'jobs', badges: { jobs: 1, report: 11, docs: 11 }, status: '1 running · 0 queued', running: true, mode: 'live' }
      : { active: 'jobs', ...live };
  }
  if (t < scene('ensemble').from) return { active: 'report', ...live };
  if (t < scene('agent').from) return { active: 'ensemble', ...live };
  return { active: 'agent', badges: { jobs: 2, report: 1, agent: 1, docs: 1 }, status: '2 running · 0 queued', running: true, mode: 'mock' };
}

// Layer completions on the card, and the run's last line on the job page, each get a tick.
const dedupe = (list: number[]) => list.filter((x, i) => i === 0 || x - list[i - 1] > 0.08);
const SFX = sfxEvents({ layerEnds: dedupe(layerEndAt), logEnds: [runEndAt] });

function Sounds() {
  const { fps } = useVideoConfig();
  return (
    <>
      <Audio src={staticFile('audio/demo-b/music.wav')} />
      {SFX.map((e, i) => {
        const from = Math.max(0, Math.round((e.at - sfxPeak(e.name)) * fps));
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(2 * fps)} layout="none">
            <Audio src={staticFile(`audio/demo-b/sfx/${e.name}.wav`)} volume={e.volume} />
          </Sequence>
        );
      })}
    </>
  );
}

export function DemoB({ debug }: DemoBProps) {
  const t = useTime();
  const navOn = Math.min(1, Math.max(0, (t - B(5)) / 0.25)) * (1 - Math.min(1, Math.max(0, (t - (B(45) - 0.2)) / 0.2)));
  return (
    <AbsoluteFill style={{ background: C.canvas }}>
      <ColdOpen t={t} />
      <NewRun t={t} />
      <JobCard t={t} />
      <JobLog t={t} />
      <Verdict t={t} />
      <Report t={t} debug={debug} />
      <Ensemble t={t} />
      <Agent t={t} />
      <Close t={t} />
      {navOn > 0 ? (
        <>
          <TopNav t={t} state={navAt(t)} opacity={navOn} />
          <BandRule opacity={navOn} />
        </>
      ) : null}
      <Captions t={t} list={CAPTIONS} />
      <Tag t={t} list={TAGS} />
      <Sounds />
      {debug ? <TargetLog /> : null}
    </AbsoluteFill>
  );
}
