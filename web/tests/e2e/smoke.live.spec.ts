import { expect, test } from '@playwright/test';

// Live mode against `pah serve` (HARNESS_API_URL). Skipped when the API is not reachable through
// the Next.js proxy.

test.beforeEach(async ({ request }) => {
  const res = await request.get('/api/harness/health', { timeout: 70_000 }).catch(() => null);
  test.skip(!res || !res.ok(), 'harness API not reachable through /api/harness');
});

test('nav shows a connected live API', async ({ page }) => {
  await page.goto('/runs/new');
  await expect(page.getByTestId('top-nav')).toBeVisible();
  await expect(page.getByTestId('api-status')).toHaveAttribute('data-state', 'connected');
});

test('/jobs renders the jobs from the API', async ({ page, request }) => {
  const jobs = await (await request.get('/api/harness/ui/jobs')).json();
  await page.goto('/jobs');
  await expect(page.getByTestId('page-jobs')).toBeVisible();
  await expect(page.getByTestId('job-card')).toHaveCount(Array.isArray(jobs) ? jobs.length : 0);
});

test('/reports/latest renders a record when a run finished', async ({ page, request }) => {
  const jobs = (await (await request.get('/api/harness/ui/jobs')).json()) as { status: string }[];
  test.skip(!jobs.some((j) => j.status === 'done'), 'no finished run');
  await page.goto('/reports/latest');
  await expect(page.getByTestId('verdict')).toBeVisible();
});
