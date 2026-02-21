/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  options: {
    tsConfig: {
      fileName: 'tsconfig.app.json',
    },
    doNotFollow: {
      path: 'node_modules',
    },
    exclude: {
      path: '(^src/test/)|(__tests__)|(\\.test\\.(ts|tsx)$)',
    },
  },
  forbidden: [
    {
      name: 'no-circular-deps',
      severity: 'error',
      from: { path: '^src' },
      to: { circular: true },
    },
    {
      name: 'no-src-to-tests',
      severity: 'error',
      from: { path: '^src/(?!.*(__tests__|\\.test\\.(ts|tsx)$)).*' },
      to: { path: '__tests__|\\.test\\.(ts|tsx)$' },
    },
  ],
}
