import type { LabelGraphResponse, LabelResponse } from '@/api/client'

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

export function computeDepths(graphData: LabelGraphResponse): Map<string, number> {
  const children = new Map<string, string[]>()
  const allIds = new Set(graphData.nodes.map((node) => node.id))
  const parentOf = new Map<string, string[]>()

  for (const edge of graphData.edges) {
    const existingChildren = children.get(edge.target)
    if (existingChildren === undefined) {
      children.set(edge.target, [edge.source])
    } else {
      existingChildren.push(edge.source)
    }

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

export function wouldCreateCycle(
  graphData: LabelGraphResponse,
  childId: string,
  proposedParentId: string,
): boolean {
  if (childId === proposedParentId) {
    return true
  }

  const children = new Map<string, string[]>()
  for (const edge of graphData.edges) {
    const existingChildren = children.get(edge.target)
    if (existingChildren === undefined) {
      children.set(edge.target, [edge.source])
    } else {
      existingChildren.push(edge.source)
    }
  }

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
