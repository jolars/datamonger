import { defineConfig } from '@playwright/test';

const baseURL = process.env.DM_DOCS_TEST_URL || 'http://127.0.0.1:8787';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  workers: 2,
  use: {
    baseURL,
    browserName: 'chromium',
    launchOptions: { executablePath: process.env.DM_CHROMIUM_PATH },
  },
  webServer: process.env.DM_DOCS_TEST_URL ? undefined : {
    command: 'python ../tools/dm_docs.py --serve --port 8787',
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    stderr: 'ignore',
  },
});
