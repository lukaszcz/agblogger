// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const CLIENT_MODULE_PATH = '../client'
type WarningProcess = {
  emitWarning(warning: string | Error): void
}
const nodeProcess = (globalThis as unknown as { process: WarningProcess }).process

function warningToMessage(warning: string | Error): string {
  return typeof warning === 'string' ? warning : warning.message
}

describe('api client bootstrap', () => {
  const originalWindow = (globalThis as { window?: unknown }).window
  const originalDocument = (globalThis as { document?: unknown }).document

  beforeEach(() => {
    vi.resetModules()
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: globalThis,
      writable: true,
    })
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { defaultView: {} } as Document,
      writable: true,
    })
  })

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow,
      writable: true,
    })
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: originalDocument,
      writable: true,
    })
  })

  it('does not emit localStorage warning when DOM is unavailable', async () => {
    const emitWarningSpy = vi
      .spyOn(nodeProcess, 'emitWarning')
      .mockImplementation(() => undefined)

    await import(`${CLIENT_MODULE_PATH}?bootstrap=${Date.now()}`)

    const didEmitLocalStorageWarning = emitWarningSpy.mock.calls
      .map((call: [string | Error]) => warningToMessage(call[0]))
      .some((message: string) => message.includes('--localstorage-file'))

    expect(didEmitLocalStorageWarning).toBe(false)
  })
})
