import type { LabelGraphResponse, LabelResponse } from '@/api/client'

/**
 * Build a map from parent label ID to its children IDs based on graph edges.
 * Edges point from child (source) to parent (target).
 */
function buildChildrenMap(edges: LabelGraphResponse['edges']): Map<string, string[]> {
  const children = new Map<string, string[]>()
  for (const edge of edges) {
    const existing = children.get(edge.target)
    if (existing === undefined) {
      children.set(edge.target, [edge.source])
    } else {
      existing.push(edge.source)
    }
  }
  return children
}

/**
 * Compute all descendant label IDs of a given label using BFS.
 * Traverses the children relationships in the label DAG.
 */
export function computeDescendants(
  labelId: string,
  labelsById: ReadonlyMap<string, Pick<LabelResponse, 'children'>>,
): Set<string> {
  const descendants = new Set<string>()
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
      if (!descendants.has(child)) {
        descendants.add(child)
        queue.push(child)
      }
    }
  }

  return descendants
}

/**
 * Compute the depth of each node in the label DAG using breadth-first traversal.
 * Root nodes (those with no parents) start at depth 0. Unreachable nodes default to depth 0.
 */
export function computeDepths(graphData: LabelGraphResponse): Map<string, number> {
  const children = buildChildrenMap(graphData.edges)
  const allIds = new Set(graphData.nodes.map((node) => node.id))
  const parentOf = new Map<string, string[]>()

  for (const edge of graphData.edges) {
    const existingParents = parentOf.get(edge.source)
    if (existingParents === undefined) {
      parentOf.set(edge.source, [edge.target])
    } else {
      existingParents.push(edge.target)
    }
  }

  const roots = [...allIds].filter((id) => !parentOf.has(id))
  const depthMap = new Map<string, number>()

  const queue = roots.map((id) => ({ id, depth: 0 }))
  while (queue.length > 0) {
    const next = queue.shift()
    if (next === undefined) {
      break
    }

    const { id, depth } = next
    if (depthMap.has(id)) {
      continue
    }

    depthMap.set(id, depth)
    for (const child of children.get(id) ?? []) {
      queue.push({ id: child, depth: depth + 1 })
    }
  }

  for (const id of allIds) {
    if (!depthMap.has(id)) {
      depthMap.set(id, 0)
    }
  }

  return depthMap
}

/**
 * Check if adding an edge from childId to proposedParentId would create a cycle.
 * Uses BFS from childId through existing children to detect if proposedParentId is reachable.
 */
export function wouldCreateCycle(
  graphData: LabelGraphResponse,
  childId: string,
  proposedParentId: string,
): boolean {
  if (childId === proposedParentId) {
    return true
  }

  const children = buildChildrenMap(graphData.edges)

  const visited = new Set<string>()
  const queue = [childId]
  while (queue.length > 0) {
    const node = queue.shift()
    if (node === undefined) {
      break
    }

    if (node === proposedParentId) {
      return true
    }

    if (visited.has(node)) {
      continue
    }

    visited.add(node)
    for (const child of children.get(node) ?? []) {
      queue.push(child)
    }
  }

  return false
}
