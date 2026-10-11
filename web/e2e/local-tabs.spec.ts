import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
const key = 'tamanegi-counterpoint-v1', id = 'species1-c-above';
async function draft(page: Page) { return page.evaluate(({ key, id }) => JSON.parse(localStorage.getItem(key)!).drafts[id], { key, id }); }
async function put(page: Page, value: number) { await page.locator('.piano-roll').click({ position: { x: 108, y: 29 + (82 - value) * 20 + 10 } }); }

test('two offline tabs preserve submissions and hints without replacing either active answer', async ({ page: a, context }) => {
  // Keep real grading but make every history upload fail, independent of server configuration.
  await context.route('**/api/history/status', route => route.fulfill({ json: { enabled: true, message: 'Test offline history' } }));
  await context.route('**/api/history/sync', route => route.abort('internetdisconnected'));
  await a.goto('./'); await expect(a.locator('.piano-roll')).toBeVisible();
  const b = await context.newPage();
  await b.goto('./'); await expect(b.locator('.piano-roll')).toBeVisible();
  const oldTabSnapshot = await b.evaluate(key => localStorage.getItem(key)!, key);
  await put(a, 72);
  await a.getByRole('button', { name: '提出して添削を受ける' }).click();
  await expect(a.getByTestId('grade-results')).toBeVisible();
  const firstId = (await draft(a)).submissions[0].id;
  await a.getByRole('button', { name: '理由を読む', exact: true }).first().click();
  await expect(a.locator('.issue-explanation').first()).toBeVisible();
  const firstHints = (await draft(a)).submissions[0].hints;
  expect(Object.keys(firstHints).length).toBeGreaterThan(0);
  await expect(a.locator('.sync-state')).toContainText('端末の履歴は保持');
  // Simulate a still-open tab running the older app, which overwrites the entire
  // storage key. The current tab must repair missing history even without a new edit.
  await b.evaluate(({ key, value }) => localStorage.setItem(key, value), { key, value: oldTabSnapshot });
  await expect.poll(async () => (await draft(a)).submissions.some((r: { id: string }) => r.id === firstId)).toBe(true);
  await put(b, 74);
  await b.locator('.feedback-tabs').getByRole('button', { name: '添削', exact: true }).click();
  await b.getByRole('button', { name: /修正して再提出|提出して添削を受ける/ }).click();
  await expect.poll(async () => (await draft(b)).submissions.length).toBe(2);
  await expect(a.getByTestId(`roll-${id}-cp-0`)).toHaveAttribute('data-midi', '72');
  await expect(b.getByTestId(`roll-${id}-cp-0`)).toHaveAttribute('data-midi', '74');
  await expect(b.locator('.sync-state')).toContainText('端末の履歴は保持');
  await a.close(); await b.reload();
  await expect(b.getByTestId(`roll-${id}-cp-0`)).toHaveAttribute('data-midi', '74');
  const saved = await draft(b);
  expect(saved.submissions).toHaveLength(2);
  expect(saved.submissions.find((r: { id: string }) => r.id === firstId).hints).toEqual(firstHints);
  await b.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await expect(b.locator('.history-card')).toHaveCount(2);
});
