// Override localStorage with a resettable mock for test isolation
export const storage = new Map<string, string>()

const mockLocalStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
  get length() {
    return storage.size
  },
  key: (index: number) => [...storage.keys()][index] ?? null,
}

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
})

// localStorage mock that throws SecurityError (for restrictive browser testing)
export const throwingLocalStorage = {
  getItem: () => {
    throw new DOMException('Access denied', 'SecurityError')
  },
  setItem: () => {
    throw new DOMException('Access denied', 'SecurityError')
  },
  removeItem: () => {
    throw new DOMException('Access denied', 'SecurityError')
  },
  clear: () => {
    throw new DOMException('Access denied', 'SecurityError')
  },
  get length() {
    return 0
  },
  key: () => null,
}
