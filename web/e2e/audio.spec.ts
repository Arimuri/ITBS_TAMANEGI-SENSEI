import { test, expect } from '@playwright/test';

test('real Web Audio keeps pitch, clock, mute, and stop tied to the answer', async ({ page, request }) => {
  await page.addInitScript(() => {
    const audit = { oscillators: [] as { node: OscillatorNode; stops: (number | undefined)[] }[], gains: [] as GainNode[], context: undefined as AudioContext | undefined };
    Object.assign(window, { __audioAudit: audit });
    const createOscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function () {
      audit.context = this;
      const node = createOscillator.call(this);
      const entry = { node, stops: [] as (number | undefined)[] };
      const stop = node.stop.bind(node);
      node.stop = (when?: number) => { entry.stops.push(when); stop(when); };
      audit.oscillators.push(entry);
      return node;
    };
    const createGain = AudioContext.prototype.createGain;
    AudioContext.prototype.createGain = function () {
      const node = createGain.call(this);
      audit.gains.push(node);
      return node;
    };
  });
  await page.goto('./');
  const exercises = await (await request.get('./api/exercises')).json();
  const exercise = exercises[0];
  const roll = page.locator('svg.piano-roll');
  await expect(roll).toBeVisible();
  await page.getByTestId(`roll-${exercise.id}-cf-0`).scrollIntoViewIfNeeded();
  const box = (await roll.boundingBox())!;
  // Add C4 (=60) in bar 2, where it does not coincide with the fixed D4.
  const maximum = Math.max(exercise.range.max, ...exercise.cantus.map((n: { pitch: { step: string; alter: number; octave: number } }) =>
    (n.pitch.octave + 1) * 12 + ({ C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[n.pitch.step] ?? 0) + n.pitch.alter)) + 1;
  await page.mouse.click(box.x + 65 + 101 + 30, box.y + 29 + (maximum - 60) * 20 + 3);
  await expect(page.getByTestId(`roll-${exercise.id}-cp-1`)).toHaveAttribute('data-midi', '60');
  await expect(page.getByTestId(`staff-${exercise.id}-cp-1`)).toHaveAttribute('data-midi', '60');

  await page.getByRole('button', { name: '再生', exact: true }).click();
  await expect(page.getByTestId('playhead')).toBeVisible();
  await expect.poll(() => page.evaluate(() => {
    const a = (window as any).__audioAudit;
    return { state: a.context.state, count: a.oscillators.length };
  })).toEqual({ state: 'running', count: exercise.cantus.length + 1 });
  const actualFrequency = await page.evaluate(() => (window as any).__audioAudit.oscillators.at(-1).node.frequency.value);
  expect(actualFrequency).toBeCloseTo(261.6256, 3);
  const headBefore = await page.getByTestId('playhead').locator('path').first().getAttribute('d');
  await expect.poll(() => page.getByTestId('playhead').locator('path').first().getAttribute('d')).not.toBe(headBefore);

  await page.getByRole('button', { name: '定旋律をミュート', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as any).__audioAudit.gains[0].gain.value)).toBeLessThan(0.001);
  await page.getByRole('button', { name: '対旋律をミュート', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as any).__audioAudit.gains[1].gain.value)).toBeLessThan(0.001);
  await page.getByRole('button', { name: '停止', exact: true }).click();
  await expect(page.getByTestId('playhead')).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__audioAudit.oscillators.every((o: any) => o.stops.length >= 2 && o.stops.at(-1) === undefined))).toBe(true);

  await page.getByLabel('Studio One音名').check();
  await expect(page.getByTestId(`roll-${exercise.id}-cp-1`)).toContainText('C3');
  await page.getByRole('button', { name: '再生', exact: true }).click();
  await expect(page.getByTestId('playhead')).toBeVisible();
  expect(await page.evaluate(() => (window as any).__audioAudit.oscillators.at(-1).node.frequency.value)).toBeCloseTo(261.6256, 3);
  await page.getByRole('button', { name: /提出して添削を受ける/ }).click();
  await expect(page.getByTestId('playhead')).toHaveCount(0);
  await expect(page.getByTestId('grade-results')).toBeVisible();
  expect(await page.evaluate(() => (window as any).__audioAudit.oscillators.every((o: any) => o.stops.length >= 2))).toBe(true);

  // Editing a sounding answer stops it; the next play uses the edited score.
  await page.getByRole('button', { name: '定旋律をミュート解除', exact: true }).click();
  await page.getByRole('button', { name: '対旋律をミュート解除', exact: true }).click();
  await page.getByRole('button', { name: '再生', exact: true }).click();
  await expect(page.getByTestId('playhead')).toBeVisible();
  await page.getByTestId(`roll-${exercise.id}-cp-1`).click();
  await page.keyboard.press('ArrowUp');
  await expect(page.getByTestId('playhead')).toHaveCount(0);
  await expect(page.getByTestId(`staff-${exercise.id}-cp-1`)).toHaveAttribute('data-midi', '62');
  await page.getByRole('button', { name: '再生', exact: true }).click();
  await expect(page.getByTestId('playhead')).toBeVisible();
  expect(await page.evaluate(() => (window as any).__audioAudit.oscillators.at(-1).node.frequency.value)).toBeCloseTo(293.6648, 3);
  await page.getByRole('button', { name: /02 · G major/ }).click();
  await expect(page.getByTestId('playhead')).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__audioAudit.oscillators.every((o: any) => o.stops.length >= 2))).toBe(true);
  await expect.poll(() => page.evaluate(() => (window as any).__audioAudit.context.state)).toBe('closed');
});
