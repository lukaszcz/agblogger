/**
 * Targeted frontend mutation profile for high-impact, already well-tested UI flows.
 */
export default {
  mutate: [
    'src/components/crosspost/CrossPostDialog.tsx',
    'src/hooks/useEditorAutoSave.ts',
    'src/pages/PostPage.tsx',
    'src/components/share/ShareButton.tsx',
    'src/components/share/ShareBar.tsx',
    'src/components/share/shareUtils.ts',
    'src/components/posts/TableOfContents.tsx',
  ],
  testRunner: 'vitest',
  coverageAnalysis: 'perTest',
  checkers: ['typescript'],
  reporters: ['clear-text', 'progress', 'html', 'json'],
  timeoutMS: 20000,
  timeoutFactor: 2.0,
  maxTestRunnerReuse: 0,
  concurrency: 4,
  vitest: {
    configFile: 'vitest.config.ts',
  },
  thresholds: {
    high: 95,
    low: 90,
    break: 90,
  },
  htmlReporter: {
    fileName: 'reports/mutation/frontend.html',
  },
  jsonReporter: {
    fileName: 'reports/mutation/frontend.json',
  },
  tempDirName: '.stryker-tmp/frontend',
}
