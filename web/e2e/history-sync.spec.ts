import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const key = 'tamanegi-counterpoint-v1';
const exerciseId = 'species1-c-above';
async function store(page: Page) { return page.evaluate(k => JSON.parse(localStorage.getItem(k)!), key); }

test('two devices migrate local history, retry failed uploads, and retain independent drafts', async ({ browser, request, baseURL }, testInfo) => {
  const status = await request.get('./api/history/status');
  test.skip(!(await status.json()).enabled, 'Run against the dedicated authenticated SQLite test server.');
  const ex = await (await request.get(`./api/exercises/${exerciseId}`)).json();
  const result = await (await request.post('./api/grade', { data: { exerciseId, notes: [], cantus: ex.cantus, ruleProfileId: ex.ruleProfileId, ruleProfileVersion: ex.ruleProfileVersion } })).json();
  const id = `migration-${crypto.randomUUID()}`;
  const record = { id, attemptId: crypto.randomUUID(), submittedAt: new Date().toISOString(), notes: [], result, hints: {} };
  const note = { id: `${exerciseId}-cp-0`, voiceId: 'cp', startTick: 0, durationTicks: 1920, pitch: { step: 'C', alter: 0, octave: 5 } };
  const initial = { version: 1, selectedExerciseId: exerciseId, drafts: { [exerciseId]: { notes: [note], attemptId: 'unsubmitted-device-a', createdAt: new Date().toISOString(), submissions: [record] } } };
  const credentials = testInfo.project.use.httpCredentials;
  const deviceA = await browser.newContext({ baseURL, httpCredentials: credentials });
  const deviceB = await browser.newContext({ baseURL, httpCredentials: credentials });
  try {
    await deviceA.addInitScript(({ key, initial }) => { if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(initial)); }, { key, initial });
    const a = await deviceA.newPage(), b = await deviceB.newPage();
    await a.goto('./');
    await expect(a.getByTestId(`roll-${exerciseId}-cp-0`)).toHaveAttribute('data-midi', '72');
    await expect.poll(async () => {
      const response = await request.post('./api/history/sync', { data: {} });
      return (await response.json()).records.some((r: { id: string }) => r.id === id);
    }).toBe(true);
    await b.goto('./');
    await expect.poll(async () => (await store(b)).drafts[exerciseId]?.submissions.some((r: { id: string }) => r.id === id)).toBe(true);
    expect((await store(b)).drafts[exerciseId].notes).toEqual([]);
    await b.locator('.feedback-tabs').getByRole('button', { name: /履歴/ }).click();
    await expect(b.locator('.history-card')).not.toHaveCount(0);
    await b.locator('.feedback-tabs').getByRole('button', { name: '添削', exact: true }).click();
    // Grading succeeds while sync alone loses connectivity. The pending record
    // must survive a page reload and upload automatically when the API recovers.
    await b.route('**/api/history/sync', route => route.abort('internetdisconnected'));
    await b.getByRole('button', { name: '提出して添削を受ける' }).click();
    await expect(b.getByTestId('grade-results')).toBeVisible();
    const afterSubmit = (await store(b)).drafts[exerciseId];
    const uploadedId = afterSubmit.submissions.find((r: { attemptId: string }) => r.attemptId === afterSubmit.attemptId).id;
    await expect(b.locator('.sync-state')).toContainText('端末の履歴は保持');
    await b.unroute('**/api/history/sync');
    await b.reload();
    await expect.poll(async () => {
      const response = await request.post('./api/history/sync', { data: {} });
      return (await response.json()).records.some((r: { id: string }) => r.id === uploadedId);
    }).toBe(true);
    await a.getByRole('button', { name: '履歴を同期', exact: true }).click();
    await expect.poll(async () => (await store(a)).drafts[exerciseId].submissions.some((r: { id: string }) => r.id === uploadedId)).toBe(true);
    const final = (await store(a)).drafts[exerciseId];
    expect(final.notes).toEqual([note]);
    expect(final.attemptId).toBe('unsubmitted-device-a');
    expect(final.submissions.filter((r: { id: string }) => r.id === id)).toHaveLength(1);
    expect(final.submissions.filter((r: { id: string }) => r.id === uploadedId)).toHaveLength(1);
    await a.reload();
    await expect(a.getByTestId(`roll-${exerciseId}-cp-0`)).toHaveAttribute('data-midi', '72');
  } finally {
    await deviceA.close(); await deviceB.close();
  }
});
