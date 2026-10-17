// File references in UI records are native API paths (/runs/{id}/files/{rel}); the browser reaches
// them through the Next.js proxy at /api/harness.

const enc = encodeURIComponent;

/** Path segments encoded one by one; empty, `.` and `..` segments are dropped. */
export function encPath(path: string): string {
  return path
    .split('/')
    .filter((s) => s && s !== '.' && s !== '..')
    .map(enc)
    .join('/');
}

/**
 * Browser URL for a file reference. Native API paths (`/runs/{id}/files/...`) get the proxy
 * prefix `base`; http(s), data and blob URLs pass through; anything else is a path relative to
 * runs/<runId>/.
 */
export function resolveFileUrl(base: string, runId: string, pathOrUrl: string): string {
  if (/^(https?:|data:|blob:)/.test(pathOrUrl)) return pathOrUrl;
  if (pathOrUrl.startsWith(`${base}/`)) return pathOrUrl;
  if (pathOrUrl.startsWith('/')) return `${base}${pathOrUrl}`;
  return `${base}/runs/${enc(runId)}/files/${encPath(pathOrUrl)}`;
}
