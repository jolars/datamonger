import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const catalog = JSON.parse(readFileSync(new URL('../site/datasets/catalog.json', import.meta.url), 'utf8'));
const defaults = catalog.datasets.filter(entry => entry.default);
const table = page => page.locator('.catalog-table');
const results = page => table(page).getByRole('link');
const openCatalog = async (page, path = '/datasets/') => {
  await page.goto(path);
  await expect(page.getByRole('search', { name: 'Dataset filters' })).toBeVisible();
};

test('searches descriptions, exact identifiers, and misspelled names', async ({ page }) => {
  await openCatalog(page);
  await expect(results(page)).toHaveCount(defaults.length);
  for (const query of ['Fisher', 'uci:iris@1', 'iriz']) {
    await page.getByLabel('Search datasets', { exact: true }).fill(query);
    await expect(results(page)).toHaveCount(1);
    await expect(results(page)).toHaveText(['Iris']);
  }
  await page.getByLabel('Search datasets', { exact: true }).fill('no-such-dataset-927341');
  await expect(table(page)).toContainText('No datasets match these filters.');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(results(page)).toHaveCount(defaults.length);
  expect(new URL(page.url()).search).toBe('');
});

test('combines categorical filters and preserves unknown task metadata', async ({ page }) => {
  await openCatalog(page);
  await page.getByLabel('Source', { exact: true }).selectOption('uci');
  await expect(results(page)).toHaveCount(defaults.filter(entry => entry.source === 'uci').length);
  await page.getByLabel('Task', { exact: true }).selectOption('classification');
  await expect(results(page)).toHaveCount(defaults.filter(entry => entry.source === 'uci' && entry.tasks.includes('classification')).length);
  await page.getByLabel('Task', { exact: true }).selectOption('unspecified');
  await expect(results(page)).toHaveText(['Wholesale Customers']);
  await expect(table(page)).toContainText('Unknown');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await page.getByLabel('Representation', { exact: true }).selectOption('sparse');
  await page.getByLabel('License', { exact: true }).selectOption('Unknown');
  await expect(results(page)).toHaveCount(defaults.filter(entry => entry.storage === 'sparse' && entry.license === 'Unknown').length);
});

test('filters dimensions, handles split ranges, and sorts numerically', async ({ page }) => {
  await openCatalog(page, '/datasets/?min_samples=1000&max_samples=2000');
  await expect(results(page)).toHaveText(['DNA Scale']);
  await expect(table(page)).toContainText('1,186–2,000');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await page.getByText('Filter by dimensions', { exact: true }).click();
  await page.getByLabel('Shape', { exact: true }).selectOption('wide');
  await page.getByLabel('Sort by', { exact: true }).selectOption('samples-asc');
  await expect(results(page)).toHaveText([
    'Colon Cancer', 'Trim32 expression in rat eye tissue', 'BRCA1 expression in TCGA breast cancer samples',
  ]);
  expect(new URL(page.url()).searchParams.get('shape')).toBe('wide');
});

test('requires all numeric filters and the task filter to match the same task', async ({ page }) => {
  const entry = {
    ...defaults[0], id: 'example:tasks@1', name: 'tasks', title: 'Different tasks',
    tasks: ['classification', 'regression'],
    dimensions: [
      { task: 'regression', type: 'regression', split: null, samples: 100, predictors: 4 },
      { task: 'classification', type: 'classification', split: null, samples: 10, predictors: 100 },
    ],
  };
  await page.route('**/datasets/catalog.json', route => route.fulfill({ json: { ...catalog, datasets: [entry] } }));
  await openCatalog(page, '/datasets/?min_samples=50&min_predictors=50');
  await expect(results(page)).toHaveCount(0);
  await page.getByLabel('Minimum predictors', { exact: true }).fill('');
  await expect(results(page)).toHaveText(['Different tasks']);
  await page.getByLabel('Task', { exact: true }).selectOption('classification');
  await expect(results(page)).toHaveCount(0);
});

test('keeps declared defaults until other versions are requested', async ({ page }) => {
  const iris = defaults.find(entry => entry.name === 'iris');
  const other = { ...iris, id: 'uci:iris@2', version: '2', default: false, url: '/datasets/uci/iris/2' };
  await page.route('**/datasets/catalog.json', route => route.fulfill({ json: { ...catalog, datasets: [iris, other] } }));
  await openCatalog(page);
  await expect(results(page)).toHaveCount(1);
  await page.getByLabel('Include other versions', { exact: true }).check();
  await expect(results(page)).toHaveCount(2);
  expect(new URL(page.url()).searchParams.get('versions')).toBe('1');
  await page.reload();
  await expect(page.getByLabel('Include other versions', { exact: true })).toBeChecked();
  await expect(results(page)).toHaveCount(2);
});

test('restores shared URLs and filters after navigating to a detail page and back', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => { window.catalogNavigationTest = true; });
  await page.locator('.desktop-sections').getByRole('link', { name: 'Datasets', exact: true }).click();
  await expect(page.getByRole('search', { name: 'Dataset filters' })).toBeVisible();
  await page.getByLabel('Search datasets', { exact: true }).fill('iris');
  await page.getByLabel('Source', { exact: true }).selectOption('uci');
  const shared = page.url();
  await table(page).getByRole('link', { name: 'Iris', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Iris', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.catalogNavigationTest)).toBe(true);
  await expect(page.locator('.desktop-sections a[aria-current=true]')).toHaveText('Datasets');
  await page.goBack();
  await expect(page.getByLabel('Search datasets', { exact: true })).toHaveValue('iris');
  await expect(page.getByLabel('Source', { exact: true })).toHaveValue('uci');
  await expect(results(page)).toHaveText(['Iris']);
  await page.goto(shared);
  await expect(results(page)).toHaveText(['Iris']);
  await expect(page.locator('.catalog-filters')).toHaveCount(1);
});

test('ignores malformed URL values and reports contradictory ranges', async ({ page }) => {
  await openCatalog(page, '/datasets/?task=made-up&min_samples=-1&sort=invalid');
  await expect(results(page)).toHaveCount(defaults.length);
  await expect(page.getByLabel('Task', { exact: true })).toHaveValue('');
  await page.getByText('Filter by dimensions', { exact: true }).click();
  await page.getByLabel('Minimum samples', { exact: true }).fill('100');
  await page.getByLabel('Maximum samples', { exact: true }).fill('10');
  await expect(page.locator('.catalog-status')).toHaveText('Minimum samples must not exceed maximum samples.');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(results(page)).toHaveCount(defaults.length);
});

test('keeps the static table available if search metadata fails to load', async ({ page }) => {
  await page.route('**/datasets/catalog.json', route => route.abort());
  await page.goto('/datasets/');
  await expect(page.locator('.catalog-status')).toContainText('Search could not load.');
  await expect(page.locator('main table').getByRole('link')).toHaveCount(defaults.length);
});

test('provides catalog navigation, details, and examples without JavaScript', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL });
  const page = await context.newPage();
  await page.goto('/datasets/');
  await expect(page.locator('main table').getByRole('link')).toHaveCount(defaults.length);
  await page.locator('main table').getByRole('link', { name: 'Iris', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Iris', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Python', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'R', exact: true })).toBeVisible();
  const metadata = await page.getByRole('link', { name: 'complete registry record', exact: true }).getAttribute('href');
  const response = await page.request.get(new URL(metadata, page.url()).href);
  expect(response.ok()).toBe(true);
  expect((await response.json()).name).toBe('iris');
  await context.close();
});

test('fits a narrow screen and loads search assets only on the catalog', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const requests = [];
  page.on('request', request => { requests.push(new URL(request.url()).pathname); });
  await page.goto('/');
  expect(requests).not.toContain('/minisearch.js');
  expect(requests).not.toContain('/datasets/catalog.json');
  await openCatalog(page);
  await expect(results(page)).toHaveCount(defaults.length);
  expect(requests).toContain('/minisearch.js');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
