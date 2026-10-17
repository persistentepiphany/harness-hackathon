import { expect, test, type Page } from '@playwright/test';

// One smoke test per route in mock mode: the nav renders with the prototype's tabs, the page's
// data-testid is present, and the API status shows mock mode. Seeded (?seed=7) for stable data.

const TABS = ['New run', 'Jobs', 'Reports', 'Ensemble', 'Agent', 'Documents'];

async function expectNav(page: Page, active: string) {
  const nav = page.getByTestId('top-nav');
  await expect(nav).toBeVisible();
  await expect(nav.getByRole('link')).toHaveText(['Harness', ...TABS.map((t) => new RegExp(`^${t}`))]);
  await expect(page.getByTestId(`nav-tab-${active}`)).toHaveAttribute('data-state', 'active');
  await expect(page.getByTestId('api-status')).toHaveAttribute('data-state', 'mock');
}

test('/ redirects to /runs/new', async ({ page }) => {
  await page.goto('/?seed=7');
  await expect(page).toHaveURL(/\/runs\/new/);
  await expectNav(page, 'new');
  await expect(page.getByTestId('page-new-run')).toBeVisible();
});

test('/runs/new', async ({ page }) => {
  await page.goto('/runs/new?seed=7');
  await expectNav(page, 'new');
  await expect(page.getByTestId('page-new-run')).toBeVisible();
  await expect(page.getByTestId('executor-chips')).toBeVisible();
});

test('/jobs lists job cards with states', async ({ page }) => {
  await page.goto('/jobs?seed=7');
  await expectNav(page, 'jobs');
  await expect(page.getByTestId('page-jobs')).toBeVisible();
  await expect(page.getByTestId('job-card')).toHaveCount(3);
  await expect(page.getByTestId('job-card').first()).toHaveAttribute('data-state', 'done');
  await expect(page.getByTestId('nav-badge-report')).toHaveText('1');
});

test('/jobs/[jobId] streams the log', async ({ page }) => {
  await page.goto('/jobs?seed=7');
  await page.getByTestId('job-card').nth(1).click();
  await expect(page).toHaveURL(/\/jobs\/run_/);
  await expectNav(page, 'jobs');
  await expect(page.getByTestId('page-job')).toBeVisible();
  await expect(page.getByTestId('log-line').first()).toBeVisible();
});

test('/reports/latest resolves to the newest finished run', async ({ page }) => {
  await page.goto('/reports/latest?seed=7');
  await expect(page).toHaveURL(/\/reports\/run_[0-9a-z_]+\?seed=7$/);
  await expectNav(page, 'report');
  await expect(page.getByTestId('page-report')).toBeVisible();
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'narrowed');
});

test('/reports/[runId]/ensemble', async ({ page }) => {
  await page.goto('/reports/latest/ensemble?seed=7');
  await expect(page).toHaveURL(/\/reports\/run_[0-9a-z_]+\/ensemble/);
  await expectNav(page, 'ensemble');
  await expect(page.getByTestId('page-ensemble')).toBeVisible();
});

test('/documents/[runId]', async ({ page }) => {
  await page.goto('/documents/latest?seed=7');
  await expect(page).toHaveURL(/\/documents\/run_/);
  await expectNav(page, 'docs');
  await expect(page.getByTestId('page-documents')).toBeVisible();
});

test('/agent', async ({ page }) => {
  await page.goto('/agent?seed=7');
  await expectNav(page, 'agent');
  await expect(page.getByTestId('page-agent')).toBeVisible();
  await expect(page.getByTestId('agent-task')).toHaveCount(3);
});
