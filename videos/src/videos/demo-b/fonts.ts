import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

// Geist and Geist Mono, the product's fonts (web/app/layout.tsx, `geist` package 1.8.1), copied into
// public/fonts by scripts/setup-assets.sh. loadFont delays rendering until both are ready.
let loaded = false;

export function loadProductFonts() {
  if (loaded) return;
  loaded = true;
  loadFont({ family: 'Geist', url: staticFile('fonts/Geist-Variable.woff2'), weight: '100 900' });
  loadFont({ family: 'Geist Mono', url: staticFile('fonts/GeistMono-Variable.woff2'), weight: '100 900' });
}
