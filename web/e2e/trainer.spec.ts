import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const id = 'species1-c-above';
async function put(page: Page, index: number, value: number) {
  const roll = page.locator('.piano-roll');
  const box = await roll.boundingBox();
  if (!box) throw Error('Piano roll not visible');
  await roll.click({ position: { x: 65 + index * 101 + 43, y: 29 + (82 - value) * 20 + 10 } });
}
test('write, select, drag, delete, undo/redo and reload one shared score', async ({ page, request }) => {
  const errors: string[] = [];
  const apiPaths: string[] = [];
  page.on('request', request => { const path = new URL(request.url()).pathname; if (path.includes('/api/')) apiPaths.push(path); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('./');
  await expect(page.getByRole('heading', { name: /C major/ })).toBeVisible();
  const apiBase = new URL('./api/', page.url()).pathname;
  expect(apiPaths.length).toBeGreaterThan(0);
  expect(apiPaths.every(path => path.startsWith(apiBase))).toBe(true);
  await expect(page.getByRole('link', { name: 'ライセンス', exact: true })).toHaveAttribute('href', new URL('./licenses/NOTICE.txt', page.url()).pathname);
  const license = await request.get('./licenses/NOTICE.txt');
  expect(license.ok()).toBe(true);
  expect(await license.text()).toContain('Bravura');
  const tempo = page.getByRole('spinbutton', { name: 'テンポ' });
  await tempo.fill(''); await tempo.pressSequentially('120'); await tempo.press('Tab');
  await expect(tempo).toHaveValue('120');
  await put(page, 0, 72);
  const roll = page.getByTestId(`roll-${id}-cp-0`), staff = page.getByTestId(`staff-${id}-cp-0`);
  await expect(roll).toHaveAttribute('data-midi', '72');
  await expect(staff).toHaveAttribute('data-midi', '72');
  await staff.click();
  await expect(roll).toHaveAttribute('data-selected', 'true');
  await expect(staff).toHaveAttribute('data-selected', 'true');
  await page.getByTestId(`roll-${id}-cf-0`).click();
  await expect(page.getByRole('button', { name: '選択した対旋律を削除' })).toBeDisabled();
  await page.keyboard.press('Delete');
  await expect(page.getByTestId(`roll-${id}-cf-0`)).toHaveAttribute('data-midi', '60');
  const rect = await roll.boundingBox();
  if (!rect) throw Error('Missing CP note');
  await page.mouse.move(rect.x + 30, rect.y + 8); await page.mouse.down(); await page.mouse.move(rect.x + 30, rect.y + 28, { steps: 5 }); await page.mouse.up();
  await expect(roll).toHaveAttribute('data-midi', '71'); // One chromatic row down is B natural.
  await expect(staff).toHaveAttribute('data-midi', '71');
  await page.getByRole('button', { name: '元に戻す', exact: true }).click();
  await expect(staff).toHaveAttribute('data-midi', '72');
  await page.getByRole('button', { name: 'やり直す', exact: true }).click();
  await expect(staff).toHaveAttribute('data-midi', '71');
  await page.getByRole('button', { name: '選択した対旋律を削除' }).click();
  await expect(roll).toHaveCount(0); await expect(staff).toHaveAttribute('data-midi', '');
  await page.getByRole('button', { name: '元に戻す', exact: true }).click();
  await page.getByRole('button', { name: '五線譜', exact: true }).click();
  await staff.click(); await page.keyboard.press('Delete'); await page.keyboard.press('ArrowUp');
  await expect(staff).toHaveAttribute('data-midi', '71');
  await page.getByRole('button', { name: '同期表示', exact: true }).click();
  await page.reload(); await expect(staff).toHaveAttribute('data-midi', '71'); await expect(roll).toHaveAttribute('data-midi', '71');
  await put(page, 1, 60);
  await expect(page.getByTestId(`roll-${id}-cp-1`)).toHaveAttribute('data-midi', '60');
  await expect(page.getByTestId(`staff-${id}-cp-1`)).toHaveAttribute('data-midi', '60');
  await page.getByLabel('Studio One音名').check();
  await expect(page.getByTestId(`roll-${id}-cp-1`)).toHaveAttribute('aria-label', /C3/);
  await expect(page.getByTestId(`staff-${id}-cp-1`)).toHaveAttribute('aria-label', /C4/);
  expect(errors).toEqual([]);
});
test('grade via real API, follow every related note, reveal hints, keep stale status and history', async ({ page }) => {
  await page.goto('./');
  await expect(page.locator('.piano-roll')).toBeVisible();
  // Two consecutive fifths intentionally produce a four-note relation; this is not a reference answer.
  await put(page, 0, 67); await put(page, 1, 69);
  await page.getByRole('button', { name: '提出して添削を受ける' }).click();
  await expect(page.getByTestId('grade-results')).toBeVisible();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('tamanegi-counterpoint-v1')!));
  const record = saved.drafts[id].submissions.at(-1);
  const issue = record.result.issues.find((i: { noteIds: string[] }) => i.noteIds.length === 4);
  expect(issue).toBeTruthy();
  await page.getByRole('button', { name: `指摘を選択: ${issue.message}`, exact: true }).first().click();
  for (const noteId of issue.noteIds) {
    await expect(page.getByTestId(`roll-${noteId}`)).toHaveAttribute('data-selected', 'true');
    await expect(page.getByTestId(`staff-${noteId}`)).toHaveAttribute('data-selected', 'true');
  }
  const issueCard = page.locator('.issue').filter({ has: page.getByRole('button', { name: `指摘を選択: ${issue.message}`, exact: true }) }).first();
  await issueCard.getByRole('button', { name: '理由を読む' }).click();
  await issueCard.getByRole('button', { name: '考えるヒントを見る' }).click();
  await expect(issueCard.locator('.issue-hint')).toBeVisible();
  await put(page, 0, 72);
  await expect(page.locator('.stale-banner')).toContainText('変更前の結果');
  await page.reload(); await expect(page.locator('.stale-banner')).toContainText('変更前の結果');
  await page.getByRole('button', { name: '修正して再提出' }).click();
  await expect(page.locator('.stale-banner')).toHaveCount(0);
  await expect(page.getByTestId('grade-results')).toContainText('まだ入力が揃っていません');
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await expect(page.locator('.history-card')).toHaveCount(2);
  await page.getByRole('button', { name: '空の回答で新しい試行' }).click();
  await expect(page.getByTestId(`roll-${id}-cp-0`)).toHaveCount(0);
  await expect(page.getByTestId('grade-results')).toHaveCount(0);
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await expect(page.locator('.history-card')).toHaveCount(2);
  await page.locator('.history-card').last().locator('summary').click();
  await expect(page.locator('.history-card').last().locator('.history-detail')).toContainText('ヒント利用 1件');
  await page.getByRole('button', { name: /G major/ }).click();
  await expect(page.getByRole('heading', { name: /G major/ })).toBeVisible();
  await expect(page.locator('[data-voice="cp"]')).toHaveCount(0);
  await page.getByRole('button', { name: /C major/ }).click();
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await expect(page.locator('.history-card')).toHaveCount(2);
});
test('rules, transposed key signatures and small screens are usable', async ({ page }) => {
  await page.goto('./');
  await page.getByRole('button', { name: '適用ルールを見る' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: /F major/ }).click();
  await expect(page.getByRole('heading', { name: /F major/ })).toBeVisible();
  await expect(page.locator('.score-sheet svg')).toBeVisible();
  await expect(page.locator('.score-error')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: '提出して添削を受ける' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('a complete independently verified answer passes, persists and leaves a private submission snapshot', async ({ page }) => {
  await page.goto('./');
  await expect(page.locator('.piano-roll')).toBeVisible();
  // Verification fixture only. No answer examples are bundled into the application or API.
  const answer = [72, 71, 74, 72, 71, 69, 71, 72];
  for (let index = 0; index < answer.length; index++) {
    await put(page, index, answer[index]);
    await expect(page.getByTestId(`staff-${id}-cp-${index}`)).toHaveAttribute('data-midi', String(answer[index]));
  }
  await expect(page.locator('.submission-progress')).toContainText('全小節の入力が揃いました');
  await page.getByRole('button', { name: '提出して添削を受ける' }).click();
  await expect(page.getByTestId('grade-results')).toContainText('今回の規則に適合しています');
  const data = await page.evaluate(() => JSON.parse(localStorage.getItem('tamanegi-counterpoint-v1')!));
  const record = data.drafts[id].submissions[0];
  expect(record.result.passed).toBe(true);
  expect(record.result.assessmentStatus).toBe('complete');
  expect(record.result.hardViolationCount).toBe(0);
  expect(record.notes).toHaveLength(8);
  await page.reload();
  await expect(page.getByTestId('grade-results')).toContainText('今回の規則に適合しています');
  await expect(page.getByTestId(`staff-${id}-cp-7`)).toHaveAttribute('data-midi', '72');
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await expect(page.locator('.history-card')).toHaveCount(1);
  await page.locator('.history-card summary').click();
  await expect(page.locator('.history-detail')).toContainText('規則に適合');
});

test('opening a submitted answer preserves the current unsent edit as a local attempt', async ({ page }) => {
  await page.goto('./'); await expect(page.locator('.piano-roll')).toBeVisible();
  await put(page, 0, 72);
  await page.getByRole('button', { name: '提出して添削を受ける' }).click();
  await expect(page.getByTestId('grade-results')).toBeVisible();
  await put(page, 0, 74);
  const before = await page.evaluate(() => JSON.parse(localStorage.getItem('tamanegi-counterpoint-v1')!).drafts['species1-c-above']);
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await page.locator('.history-card summary').click();
  await page.getByRole('button', { name: 'この回答から新しい試行' }).click();
  await expect(page.getByTestId(`roll-${id}-cp-0`)).toHaveAttribute('data-midi', '72');
  await expect(page.getByTestId('grade-results')).toHaveCount(0);
  await page.reload();
  const after = await page.evaluate(() => JSON.parse(localStorage.getItem('tamanegi-counterpoint-v1')!).drafts['species1-c-above']);
  expect(after.attemptId).not.toBe(before.attemptId);
  expect(after.submissions).toEqual(before.submissions);
  expect(after.savedAttempts[0].notes).toEqual(before.notes);
  await page.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
  await page.locator('.saved-attempt').getByRole('button', { name: '再開', exact: true }).click();
  await expect(page.getByTestId(`roll-${id}-cp-0`)).toHaveAttribute('data-midi', '74');
  await expect(page.getByTestId(`staff-${id}-cp-0`)).toHaveAttribute('data-midi', '74');
});
