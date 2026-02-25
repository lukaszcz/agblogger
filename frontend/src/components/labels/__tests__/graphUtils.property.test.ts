import { describe, expect, it } from 'vitest'
import fc from 'fast-check'

import type { LabelGraphResponse, LabelResponse } from '@/api/client'
import {
  computeDepths,
  computeDescendants,
  wouldCreateCycle,
} from '@/components/labels/graphUtils'

const idChars = 'abcdefghijklmnopqrstuvwxyz0123456789'.split('')

const idArb = fc
  .array(fc.constantFrom(...idChars), { minLength: 1, maxLength: 8 })
  .map((chars) => chars.join(''))

const graphArb: fc.Arbitrary<LabelGraphResponse> = fc
  .uniqueArray(idArb, { minLength: 1, maxLength: 8 })
  .chain((nodeIds) => {
    const nodes = nodeIds.map((id) => ({ id, names: [id], post_count: 0 }))
    if (nodeIds.length < 2) {
      return fc.constant({ nodes, edges: [] })
    }

    const edgeArb = fc
      .tuple(fc.constantFrom(...nodeIds), fc.constantFrom(...nodeIds))
      .filter(([source, target]) => source !== target)
      .map(([source, target]) => ({ source, target }))

    const maxEdges = Math.min(nodeIds.length * (nodeIds.length - 1), 20)

    return fc
      .uniqueArray(edgeArb, { minLength: 0, maxLength: maxEdges })
      .map((edges) => ({ nodes, edges }))
  })

function toChildrenMap(graph: LabelGraphResponse): Map<string, string[]> {
  const children = new Map<string, string[]>()

  for (const node of graph.nodes) {
    children.set(node.id, [])
  }

  for (const edge of graph.edges) {
    const existing = children.get(edge.target)
    if (existing !== undefined) {
      existing.push(edge.source)
    }
  }

  return children
}

function referenceWouldCreateCycle(
  graph: LabelGraphResponse,
  childId: string,
  proposedParentId: string,
): boolean {
  if (childId === proposedParentId) {
    return true
  }

  const children = toChildrenMap(graph)
  const visited = new Set<string>()
  const queue = [childId]

  while (queue.length > 0) {
    const next = queue.shift()
    if (next === undefined) {
      break
    }
    if (next === proposedParentId) {
      return true
    }
    if (visited.has(next)) {
      continue
    }
    visited.add(next)
    for (const child of children.get(next) ?? []) {
      queue.push(child)
    }
  }

  return false
}

function referenceComputeDepths(graph: LabelGraphResponse): Map<string, number> {
  const children = toChildrenMap(graph)
  const parentOf = new Map<string, string[]>()
  for (const edge of graph.edges) {
    const parents = parentOf.get(edge.source)
    if (parents === undefined) {
      parentOf.set(edge.source, [edge.target])
    } else {
      parents.push(edge.target)
    }
  }

  const allIds = graph.nodes.map((node) => node.id)
  const roots = allIds.filter((id) => !parentOf.has(id))
  if (roots.length === 0) {
    return new Map(allIds.map((id) => [id, 0]))
  }

  const dist = new Map<string, number>(allIds.map((id) => [id, Number.POSITIVE_INFINITY]))
  const queue = roots.map((id) => ({ id, depth: 0 }))

  while (queue.length > 0) {
    const next = queue.shift()
    if (next === undefined) {
      break
    }

    const currentBest = dist.get(next.id)
    if (currentBest === undefined || next.depth >= currentBest) {
      continue
    }

    dist.set(next.id, next.depth)
    for (const child of children.get(next.id) ?? []) {
      queue.push({ id: child, depth: next.depth + 1 })
    }
  }

  const result = new Map<string, number>()
  for (const id of allIds) {
    const depth = dist.get(id)
    if (depth === undefined || !Number.isFinite(depth)) {
      result.set(id, 0)
    } else {
      result.set(id, depth)
    }
  }
  return result
}

function graphToLabelsById(graph: LabelGraphResponse): Map<string, LabelResponse> {
  const childrenMap = toChildrenMap(graph)
  const parentMap = new Map<string, string[]>()

  for (const node of graph.nodes) {
    parentMap.set(node.id, [])
  }

  for (const edge of graph.edges) {
    const parents = parentMap.get(edge.source)
    if (parents !== undefined) {
      parents.push(edge.target)
    }
  }

  return new Map(
    graph.nodes.map((node) => {
      const parents = parentMap.get(node.id) ?? []
      const children = childrenMap.get(node.id) ?? []
      const label: LabelResponse = {
        id: node.id,
        names: [node.id],
        is_implicit: false,
        parents,
        children,
        post_count: 0,
      }
      return [node.id, label]
    }),
  )
}

function referenceDescendants(labelId: string, labelsById: Map<string, LabelResponse>): Set<string> {
  const descendants = new Set<string>()
  const visited = new Set<string>([labelId])
  const queue = [labelId]

  while (queue.length > 0) {
    const current = queue.shift()
    if (current === undefined) {
      break
    }
    const label = labelsById.get(current)
    if (label === undefined) {
      continue
    }

    for (const child of label.children) {
      if (!visited.has(child)) {
        visited.add(child)
        descendants.add(child)
        queue.push(child)
      }
    }
  }

  return descendants
}

function pickId(ids: string[], index: number): string {
  const id = ids[index % ids.length]
  if (id === undefined) {
    throw new Error('Expected a non-empty node id list')
  }
  return id
}

describe('label graph property tests', () => {
  it('wouldCreateCycle matches reference reachability logic', () => {
    fc.assert(
      fc.property(graphArb, fc.nat({ max: 200 }), fc.nat({ max: 200 }), (graph, a, b) => {
        const ids = graph.nodes.map((node) => node.id)
        const child = pickId(ids, a)
        const parent = pickId(ids, b)

        const expected = referenceWouldCreateCycle(graph, child, parent)
        const actual = wouldCreateCycle(graph, child, parent)

        expect(actual).toBe(expected)
      }),
      { numRuns: 400 },
    )
  })

  it('computeDepths matches shortest-root-distance reference implementation', () => {
    fc.assert(
      fc.property(graphArb, (graph) => {
        const expected = referenceComputeDepths(graph)
        const actual = computeDepths(graph)

        expect(actual.size).toBe(expected.size)

        for (const node of graph.nodes) {
          const actualDepth = actual.get(node.id)
          const expectedDepth = expected.get(node.id)
          expect(actualDepth).toBe(expectedDepth)
          expect(actualDepth).toBeGreaterThanOrEqual(0)
          expect(Number.isInteger(actualDepth)).toBe(true)
        }
      }),
      { numRuns: 300 },
    )
  })

  it('computeDescendants exactly matches BFS descendants over children edges', () => {
    fc.assert(
      fc.property(graphArb, fc.nat({ max: 200 }), (graph, index) => {
        const ids = graph.nodes.map((node) => node.id)
        const startId = pickId(ids, index)
        const labelsById = graphToLabelsById(graph)

        const expected = referenceDescendants(startId, labelsById)
        const actual = computeDescendants(startId, labelsById)

        expect(actual).toEqual(expected)

        for (const id of actual) {
          expect(labelsById.has(id)).toBe(true)
        }
      }),
      { numRuns: 350 },
    )
  })
})
