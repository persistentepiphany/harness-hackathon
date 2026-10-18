import type { NextConfig } from 'next';

// /api/harness/* is proxied to `pah serve` by the streaming route handler in
// app/api/harness/[...path]/route.ts, which reads HARNESS_API_URL per request (a next.config
// rewrite would fix the destination at build time). See docs/UI.md.
const nextConfig: NextConfig = {
  // No dev overlay badge: it covers screenshots and recordings.
  devIndicators: false,
  // Separate build directories let several dev servers run side by side.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // Vercel: default output. Modal (deploy/modal/web_app.py): NEXT_OUTPUT=standalone.
  output: process.env.NEXT_OUTPUT === 'standalone' ? 'standalone' : undefined,
  reactStrictMode: true,
  // `next dev` blocks dev resources (HMR, chunks) for hosts other than localhost; tests and
  // screenshots use 127.0.0.1.
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  poweredByHeader: false,
  transpilePackages: ['molstar'],
  // web/ has its own lockfile next to the repository's; pin the workspace root to web/.
  turbopack: {
    root: __dirname,
    // Mol* (molstar/lib/apps/viewer) pulls in h264-mp4-encoder's Node build, which requires
    // Node built-ins; give the browser bundle empty modules for them.
    resolveAlias: {
      fs: { browser: './lib/shims/empty.js' },
      path: { browser: './lib/shims/empty.js' },
      crypto: { browser: './lib/shims/empty.js' },
    },
  },
  experimental: {
    // Route types are referenced from next-env.d.ts instead of per-distDir tsconfig includes, so
    // builds with different NEXT_DIST_DIR values do not rewrite tsconfig.json.
    strictRouteTypes: true,
  },
};

export default nextConfig;
