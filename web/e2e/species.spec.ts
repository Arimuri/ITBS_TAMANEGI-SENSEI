import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { Exercise } from '../src/model';
import { midi } from '../src/model';

async function enter(page: Page, exercise: Exercise, index: number, value: number) {
  const slot = exercise.noteSlots![index];
  const cell = exercise.species === 2 || exercise.species === 4 ? 148 : 196;
  const maximum = Math.max(exercise.range.max, ...exercise.cantus.map(n => midi(n.pitch))) + 1;
  const x = 65 + (slot.startTick + Math.min(100, slot.durationTicks / 4)) / (exercise.ppq * 4) * cell;
  const scroll = page.getByTestId('piano-scroll');
  await scroll.evaluate((element, left) => { element.scrollLeft = Math.max(0, left - element.clientWidth / 2); }, x);
  const roll = page.locator('.piano-roll');
  await roll.scrollIntoViewIfNeeded();
  const bounds = (await roll.boundingBox())!;
  await page.mouse.click(bounds.x + x, bounds.y + 29 + (maximum - value) * 20 + 10);
  await expect(page.getByTestId(`roll-${exercise.id}-cp-${index}`)).toHaveAttribute('data-midi', String(value));
}

for (const species of [2, 3, 4, 5]) test(`species ${species}: prescribed rhythm, shared score, grading and reload`, async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const exercises: Exercise[] = await (await request.get('./api/exercises')).json();
  const exercise = exercises.find(e => e.species === species)!;
  expect(exercise).toBeTruthy();
  await page.goto('./');
  await page.getByRole('button', { name: `第${species}種`, exact: true }).click();
  await expect(page.getByRole('heading', { name: exercise.title, exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'この課題の進め方' })).toContainText(exercise.brief!.rhythm);
  if (species === 5) await expect(page.locator('.lesson-brief')).toContainText('固定リズム');
  for (let index = 0; index < exercise.noteSlots!.length; index++) {
    // Intentionally repeated pitches exercise the full time grid, not a model answer.
    await enter(page, exercise, index, 72);
    const slot = exercise.noteSlots![index];
    await expect(page.getByTestId(`roll-${exercise.id}-cp-${index}`)).toHaveAttribute('data-start-tick', String(slot.startTick));
    await expect(page.getByTestId(`roll-${exercise.id}-cp-${index}`)).toHaveAttribute('data-duration-ticks', String(slot.durationTicks));
  }
  await expect(page.locator('.score-error')).toHaveCount(0);
  await expect(page.locator('.submission-progress')).toContainText('すべての入力枠が揃いました');
  const crossing = exercise.noteSlots!.findIndex(s => Math.floor(s.startTick / 1920) !== Math.floor((s.startTick + s.durationTicks - 1) / 1920));
  if (crossing >= 0) {
    const tie = page.getByTestId(`staff-${exercise.id}-cp-${crossing}`);
    await expect(tie).toHaveCount(2);
    await expect(tie.first()).toHaveAttribute('data-tie-to', 'true');
    await expect(tie.last()).toHaveAttribute('data-tie-from', 'true');
    await tie.last().click();
    await page.keyboard.press('ArrowUp');
    for (const fragment of await tie.all()) { await expect(fragment).toHaveAttribute('data-midi', '74'); await expect(fragment).toHaveAttribute('data-selected', 'true'); }
    await expect(page.getByTestId(`roll-${exercise.id}-cp-${crossing}`)).toHaveAttribute('data-midi', '74');
    await page.getByRole('button', { name: '元に戻す', exact: true }).click();
    await expect(tie.first()).toHaveAttribute('data-midi', '72');
  }
  await page.getByRole('button', { name: '適用ルールを見る' }).click();
  await expect(page.getByRole('dialog')).toContainText('RULE PROFILE · v2');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '提出して添削を受ける' }).click();
  await expect(page.getByTestId('grade-results')).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('tamanegi-counterpoint-v1')!));
  const record = stored.drafts[exercise.id].submissions.at(-1);
  expect(record.result.assessmentStatus).toBe('complete');
  expect(record.result.ruleProfileVersion).toBe('2');
  expect(record.notes.map((n: { startTick: number; durationTicks: number }) => ({ startTick: n.startTick, durationTicks: n.durationTicks }))).toEqual(exercise.noteSlots);
  await page.reload();
  await expect(page.getByTestId('grade-results')).toBeVisible();
  await expect(page.locator('[data-voice="cp"]')).toHaveCount(exercise.noteSlots!.length);
  await expect(page.locator('.score-error')).toHaveCount(0);
  await page.getByRole('button', { name: '第1種', exact: true }).click();
  await page.getByRole('button', { name: '適用ルールを見る' }).click();
  await expect(page.getByRole('dialog')).toContainText('RULE PROFILE · v1');
  expect(errors).toEqual([]);
});

test('a tied note sounds once for its full duration after the initial rest', async ({ page, request }) => {
  await page.addInitScript(() => {
    const audit: { starts: number[]; stops: number[] }[] = [];
    Object.assign(window, { __tieAudio: audit });
    const create = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function () {
      const node = create.call(this), entry = { starts: [] as number[], stops: [] as number[] };
      const start = node.start.bind(node), stop = node.stop.bind(node);
      node.start = when => { entry.starts.push(when ?? 0); start(when); };
      node.stop = when => { if (when !== undefined) entry.stops.push(when); stop(when); };
      audit.push(entry); return node;
    };
  });
  const exercises: Exercise[] = await (await request.get('./api/exercises')).json();
  const exercise = exercises.find(e => e.species === 4)!;
  await page.goto('./'); await page.getByRole('button', { name: '第4種', exact: true }).click();
  await expect(page.locator('.piano-roll')).toBeVisible();
  // The opening half rest rejects editing; the first actual input starts on beat 3.
  const roll = page.locator('.piano-roll'), maximum = exercise.range.max + 1;
  await roll.click({ position: { x: 65 + 20, y: 29 + (maximum - 72) * 20 + 10 } });
  await expect(page.locator('[data-voice="cp"]')).toHaveCount(0);
  await enter(page, exercise, 0, 72);
  await page.getByRole('button', { name: '再生', exact: true }).click();
  await expect(page.getByTestId('playhead')).toBeVisible();
  const audit = await page.evaluate(() => (window as any).__tieAudio);
  expect(audit).toHaveLength(exercise.cantus.length + 1);
  const cp = audit.at(-1);
  expect(cp.starts).toHaveLength(1);
  expect(cp.starts[0] - audit[0].starts[0]).toBeCloseTo(60 / exercise.tempo * 2, 5);
  expect(cp.stops[0] - cp.starts[0]).toBeCloseTo(60 / exercise.tempo * 4 + 0.01, 5);
  await page.getByRole('button', { name: '停止', exact: true }).click();
  await expect(page.getByTestId('playhead')).toHaveCount(0);
});

test('dotted mixed-rhythm fragments render without a tick mismatch', async ({ page }) => {
  // A future compatible 3+1-beat exercise checks the renderer independently of today's catalog.
  await page.route('**/api/exercises', async route => {
    const response = await route.fetch(), exercises: Exercise[] = await response.json();
    const exercise = exercises.find(e => e.species === 5)!;
    exercise.noteSlots = [{ startTick: 0, durationTicks: 1440 }, { startTick: 1440, durationTicks: 480 }, ...exercise.noteSlots!.filter(s => s.startTick >= 1920)];
    await route.fulfill({ response, json: exercises });
  });
  await page.goto('./'); await page.getByRole('button', { name: '第5種', exact: true }).click();
  await expect(page.getByTestId('staff-species5-c-above-cp-0')).toHaveAttribute('data-duration-ticks', '1440');
  await expect(page.getByTestId('staff-species5-c-above-cp-1')).toHaveAttribute('data-duration-ticks', '480');
  await expect(page.locator('.score-error')).toHaveCount(0);
});
