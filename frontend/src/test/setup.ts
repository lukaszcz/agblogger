import '@testing-library/jest-dom/vitest'

const WARNING_GUARD_KEY = '__agblogger_warning_guard_installed__'
type WarningProcess = {
  on(event: 'warning', listener: (warning: Error) => void): void
}
const nodeProcess = (globalThis as unknown as { process: WarningProcess }).process

if (!(WARNING_GUARD_KEY in globalThis)) {
  Object.defineProperty(globalThis, WARNING_GUARD_KEY, {
    configurable: false,
    enumerable: false,
    value: true,
    writable: false,
  })

  nodeProcess.on('warning', (warning: Error) => {
    throw new Error(
      `Node warning during vitest run (${warning.name}): ${warning.message}\n${warning.stack ?? ''}`,
    )
  })
}
