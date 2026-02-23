import { describe, it, expect, beforeEach } from 'vitest'
import { storage, throwingLocalStorage } from './testUtils'

describe('mock localStorage', () => {
  beforeEach(() => {
    storage.clear()
  })

  it('getItem returns null for missing keys', () => {
    expect(localStorage.getItem('nonexistent')).toBeNull()
  })

  it('setItem and getItem round-trip', () => {
    localStorage.setItem('key', 'value')
    expect(localStorage.getItem('key')).toBe('value')
  })

  it('removeItem deletes a key', () => {
    localStorage.setItem('key', 'value')
    localStorage.removeItem('key')
    expect(localStorage.getItem('key')).toBeNull()
  })

  it('clear removes all keys', () => {
    localStorage.setItem('a', '1')
    localStorage.setItem('b', '2')
    localStorage.clear()
    expect(localStorage.getItem('a')).toBeNull()
    expect(localStorage.length).toBe(0)
  })

  it('length reflects number of stored keys', () => {
    expect(localStorage.length).toBe(0)
    localStorage.setItem('a', '1')
    expect(localStorage.length).toBe(1)
    localStorage.setItem('b', '2')
    expect(localStorage.length).toBe(2)
  })

  it('key returns key name by index', () => {
    localStorage.setItem('alpha', '1')
    localStorage.setItem('beta', '2')
    const keys = [localStorage.key(0), localStorage.key(1)]
    expect(keys).toContain('alpha')
    expect(keys).toContain('beta')
  })

  it('key returns null for out-of-range index', () => {
    expect(localStorage.key(999)).toBeNull()
  })
})

describe('throwingLocalStorage', () => {
  it('getItem throws SecurityError', () => {
    expect(() => throwingLocalStorage.getItem()).toThrow('Access denied')
  })

  it('setItem throws SecurityError', () => {
    expect(() => throwingLocalStorage.setItem()).toThrow('Access denied')
  })

  it('removeItem throws SecurityError', () => {
    expect(() => throwingLocalStorage.removeItem()).toThrow('Access denied')
  })

  it('clear throws SecurityError', () => {
    expect(() => throwingLocalStorage.clear()).toThrow('Access denied')
  })

  it('length returns 0', () => {
    expect(throwingLocalStorage.length).toBe(0)
  })

  it('key returns null', () => {
    expect(throwingLocalStorage.key()).toBeNull()
  })
})
