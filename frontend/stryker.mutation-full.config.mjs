/**
 * Full frontend mutation profile for broad nightly sweeps.
 */
export default {
  mutate: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.test.{ts,tsx}',
    '!src/**/__tests__/**',
    '!src/test/**',
    '!src/main.tsx',
    '!src/**/*.d.ts',
  ],
  testRunner: 'vitest',
  coverageAnalysis: 'perTest',
  checkers: ['typescript'],
  reporters: ['clear-text', 'progress', 'html', 'json'],
  timeoutMS: 30000,
  timeoutFactor: 2.5,
  maxTestRunnerReuse: 0,
  concurrency: 4,
  vitest: {
    configFile: 'vitest.config.ts',
  },
  thresholds: {
    high: 85,
    low: 75,
    break: 75,
  },
  htmlReporter: {
    fileName: 'reports/mutation/frontend-full.html',
  },
  jsonReporter: {
    fileName: 'reports/mutation/frontend-full.json',
  },
  tempDirName: '.stryker-tmp/frontend-full',
}
