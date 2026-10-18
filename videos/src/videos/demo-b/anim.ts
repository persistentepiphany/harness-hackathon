import { Easing } from 'remotion';

import { clamp01 } from '../../kit/time';

// The product's own motion (web/app/globals.css): fadeUp and fadeIn 0.3 s ease-out, spin 0.8 s
// linear, pulse 1.2 s. Here they are functions of time instead of CSS keyframes.

const easeOut = Easing.bezier(0, 0, 0.58, 1);
const easeInOut = Easing.bezier(0.42, 0, 0.58, 1);

/** fadeUp: opacity 0 to 1, translateY 5 px to 0, over 0.3 s from `start`. */
export function fadeUp(t: number, start: number, distance = 5) {
  const u = easeOut(clamp01((t - start) / 0.3));
  return { opacity: u, translate: `0 ${(1 - u) * distance}px` };
}

/** fadeIn: opacity 0 to 1 over 0.3 s. */
export function fadeIn(t: number, start: number, length = 0.3) {
  return { opacity: easeOut(clamp01((t - start) / length)) };
}

/** Linear 0 to 1. */
export const lin = (t: number, start: number, length: number) => clamp01((t - start) / length);

/** Eased 0 to 1 (ease-in-out), for counters and scroll offsets. */
export const ease = (t: number, start: number, length: number) => easeInOut(clamp01((t - start) / length));

/** spin 0.8 s linear: degrees at time t. */
export const spinDeg = (t: number) => ((t / 0.8) % 1) * 360;

/** pulse 1.2 s: opacity 1, 0.3 at the middle, 1. */
export const pulse = (t: number, period = 1.2) => 0.65 + 0.35 * Math.cos((2 * Math.PI * t) / period);

/** Scene window blur swap: in over 0.18 s from `from`, out over 0.12 s before `to`. */
export function swap(t: number, from: number, to: number, inLen = 0.18, outLen = 0.12) {
  const enter = from <= 0 ? 1 : clamp01((t - from) / inLen);
  const leave = to === Infinity ? 0 : clamp01((t - (to - outLen)) / outLen);
  const v = enter * (1 - leave);
  return { opacity: v, filter: v < 1 ? `blur(${(1 - v) * 8}px)` : undefined };
}

/** Land a word: blur in from 16 px, rise 36 px, 0.3 s on cubic-bezier(0.22, 1, 0.36, 1). */
const land = Easing.bezier(0.22, 1, 0.36, 1);
export function landWord(t: number, at: number, rise = 36) {
  const u = land(clamp01((t - at) / 0.3));
  return { opacity: u, filter: u < 1 ? `blur(${(1 - u) * 16}px)` : undefined, translate: `0 ${(1 - u) * rise}px` };
}
