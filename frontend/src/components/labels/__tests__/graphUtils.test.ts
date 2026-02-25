import { describe, it, expect } from 'vitest'
import type { LabelResponse } from '@/api/client'
import { computeDescendants } from '@/components/labels/graphUtils'

describe('computeDescendants', () => {
  it('does not include the starting label in its own descendants even with cycles', () => {
    // Create a cycle: A -> B -> A (A has child B, B has child A)
    const labelsById = new Map<string, Pick<LabelResponse, 'children'>>([
      ['A', { children: ['B'] }],
      ['B', { children: ['A'] }],
    ])
    const descendants = computeDescendants('A', labelsById)
    expect(descendants.has('B')).toBe(true)
    expect(descendants.has('A')).toBe(false) // A should NOT be in its own descendants
  })

  it('terminates and excludes self in larger cycles', () => {
    // A -> B -> C -> A
    const labelsById = new Map<string, Pick<LabelResponse, 'children'>>([
      ['A', { children: ['B'] }],
      ['B', { children: ['C'] }],
      ['C', { children: ['A'] }],
    ])
    const descendants = computeDescendants('A', labelsById)
    expect(descendants).toEqual(new Set(['B', 'C']))
    expect(descendants.has('A')).toBe(false)
  })

  it('handles simple tree without cycles', () => {
    const labelsById = new Map<string, Pick<LabelResponse, 'children'>>([
      ['root', { children: ['a', 'b'] }],
      ['a', { children: ['c'] }],
      ['b', { children: [] }],
      ['c', { children: [] }],
    ])
    const descendants = computeDescendants('root', labelsById)
    expect(descendants).toEqual(new Set(['a', 'b', 'c']))
  })

  it('returns empty set for leaf node', () => {
    const labelsById = new Map<string, Pick<LabelResponse, 'children'>>([
      ['leaf', { children: [] }],
    ])
    const descendants = computeDescendants('leaf', labelsById)
    expect(descendants.size).toBe(0)
  })
})
