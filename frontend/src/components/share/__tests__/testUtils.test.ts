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
  it('getItem throws "Access denied"', () => {
    expect(() => throwingLocalStorage.getItem('key')).toThrow('Access denied')
  })

  it('setItem throws "Access denied"', () => {
    expect(() => throwingLocalStorage.setItem('key', 'value')).toThrow('Access denied')
  })

  it('removeItem throws "Access denied"', () => {
    expect(() => throwingLocalStorage.removeItem('key')).toThrow('Access denied')
  })

  it('clear throws "Access denied"', () => {
    expect(() => throwingLocalStorage.clear()).toThrow('Access denied')
  })

  it('length returns 0', () => {
    expect(throwingLocalStorage.length).toBe(0)
  })

  it('key returns null', () => {
    expect(throwingLocalStorage.key(0)).toBeNull()
  })
})
