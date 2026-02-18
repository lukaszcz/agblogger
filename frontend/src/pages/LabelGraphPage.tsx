import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type Connection,
  useNodesState,
  useEdgesState,
  type NodeTypes,
  type NodeProps,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Dagre from '@dagrejs/dagre'
import { Search, GitFork } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { fetchLabel, fetchLabelGraph, updateLabel } from '@/api/labels'
import { HTTPError } from '@/api/client'
import type { LabelGraphResponse } from '@/api/client'

/* ── Types ─────────────────────────────────────────── */

interface LabelNodeData {
  label: string
  names: string[]
  postCount: number
  depth: number
}

/* ── Custom node ────────────────────────────────────── */

function LabelNode({ data }: NodeProps) {
  const d = data as unknown as LabelNodeData
  const depthColors = [
    'border-accent bg-accent/8 text-accent',
    'border-amber-600 bg-amber-50 text-amber-800',
    'border-emerald-600 bg-emerald-50 text-emerald-800',
    'border-sky-600 bg-sky-50 text-sky-800',
    'border-violet-600 bg-violet-50 text-violet-800',
  ]
  const style = depthColors[d.depth % depthColors.length]

  return (
    <div
      className={`rounded-lg border-2 px-4 py-2.5 shadow-sm cursor-pointer
        transition-all hover:shadow-md hover:scale-[1.04] ${style}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-border-dark !w-2 !h-2" />
      <div className="font-display text-base leading-tight">#{d.label}</div>
      {d.names.length > 0 && (
        <div className="text-xs opacity-70 mt-0.5 max-w-[140px] truncate">
          {d.names[0]}
        </div>
      )}
      <div className="text-[10px] mt-1.5 font-mono opacity-60">
        {d.postCount} {d.postCount === 1 ? 'post' : 'posts'}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-border-dark !w-2 !h-2" />
    </div>
  )
}

const nodeTypes: NodeTypes = { label: LabelNode }

/* ── Dagre layout ───────────────────────────────────── */

function layoutGraph(
  graphData: LabelGraphResponse,
  depthMap: Map<string, number>,
  isEditable: boolean,
): { nodes: Node[]; edges: Edge[] } {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 50, edgesep: 30 })

  for (const node of graphData.nodes) {
    g.setNode(node.id, { width: 160, height: 80 })
  }

  for (const edge of graphData.edges) {
    // edge.source = child, edge.target = parent
    // for dagre: parent -> child (top-down)
    g.setEdge(edge.target, edge.source)
  }

  Dagre.layout(g)

  const nodes: Node[] = graphData.nodes.map((n) => {
    const pos = g.node(n.id) as { x: number; y: number }
    return {
      id: n.id,
      type: 'label',
      position: { x: pos.x - 80, y: pos.y - 40 },
      data: {
        label: n.id,
        names: n.names,
        postCount: n.post_count,
        depth: depthMap.get(n.id) ?? 0,
      },
    }
  })

  const edgeColor = '#c8c1b8'
  const edges: Edge[] = graphData.edges.map((e) => ({
    id: `${e.target}-${e.source}`,
    source: e.target,
    target: e.source,
    animated: false,
    style: { stroke: edgeColor, strokeWidth: 2, ...(isEditable ? { cursor: 'pointer' } : {}) },
    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor, width: 16, height: 16 },
    interactionWidth: isEditable ? 20 : 0,
  }))

  return { nodes, edges }
}

/* ── Depth computation ──────────────────────────────── */

function computeDepths(graphData: LabelGraphResponse): Map<string, number> {
  const children = new Map<string, string[]>()
  const allIds = new Set(graphData.nodes.map((n) => n.id))
  const parentOf = new Map<string, string[]>()

  for (const e of graphData.edges) {
    if (!children.has(e.target)) children.set(e.target, [])
    children.get(e.target)!.push(e.source)

    if (!parentOf.has(e.source)) parentOf.set(e.source, [])
    parentOf.get(e.source)!.push(e.target)
  }

  // Roots = nodes with no parents
  const roots = [...allIds].filter((id) => !parentOf.has(id))
  const depthMap = new Map<string, number>()

  const queue = roots.map((id) => ({ id, depth: 0 }))
  while (queue.length > 0) {
    const { id, depth } = queue.shift()!
    if (depthMap.has(id)) continue
    depthMap.set(id, depth)
    for (const child of children.get(id) ?? []) {
      queue.push({ id: child, depth: depth + 1 })
    }
  }

  // Fallback for disconnected nodes
  for (const id of allIds) {
    if (!depthMap.has(id)) depthMap.set(id, 0)
  }

  return depthMap
}

/* ── Cycle detection ────────────────────────────────── */

/**
 * Check if adding childId -> proposedParentId would create a cycle.
 * BFS from childId following children edges. If proposedParentId is found
 * as a descendant of childId, the connection would create a cycle.
 */
function wouldCreateCycle(
  graphData: LabelGraphResponse,
  childId: string,
  proposedParentId: string,
): boolean {
  if (childId === proposedParentId) return true
  // Build children map: parent -> list of children
  const children = new Map<string, string[]>()
  for (const e of graphData.edges) {
    // edge.source = child, edge.target = parent
    // So if target is the parent, source is the child
    if (!children.has(e.target)) children.set(e.target, [])
    children.get(e.target)!.push(e.source)
  }
  // BFS from childId to see if proposedParentId is a descendant
  const visited = new Set<string>()
  const queue = [childId]
  while (queue.length > 0) {
    const node = queue.shift()!
    if (node === proposedParentId) return true
    if (visited.has(node)) continue
    visited.add(node)
    for (const child of children.get(node) ?? []) {
      queue.push(child)
    }
  }
  return false
}

/* ── Main component ────────────────────────────────── */

export default function LabelGraphPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [graphData, setGraphData] = useState<LabelGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [mutating, setMutating] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLabelGraph()
      .then(setGraphData)
      .catch((err) => {
        if (err instanceof HTTPError && err.response.status === 401) {
          setError('Session expired. Please log in to view the graph.')
        } else {
          setError('Failed to load label graph. Please try again later.')
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const depthMap = useMemo(
    () => (graphData ? computeDepths(graphData) : new Map<string, number>()),
    [graphData],
  )

  useEffect(() => {
    if (!graphData) return
    const { nodes: n, edges: e } = layoutGraph(graphData, depthMap, !!user)
    setNodes(n)
    setEdges(e)
  }, [graphData, depthMap, setNodes, setEdges, user])

  // Search highlight
  const filteredNodes = useMemo(() => {
    if (!search.trim()) return nodes
    const q = search.toLowerCase()
    return nodes.map((n) => {
      const d = n.data as unknown as LabelNodeData
      const match =
        d.label.toLowerCase().includes(q) ||
        d.names.some((name: string) => name.toLowerCase().includes(q))
      return {
        ...n,
        style: match ? {} : { opacity: 0.2 },
      }
    })
  }, [nodes, search])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      void navigate(`/labels/${node.id}`)
    },
    [navigate],
  )

  const isValidConnection = useCallback(
    (connection: { source: string | null; target: string | null }) => {
      if (!graphData || !connection.source || !connection.target) return false
      if (connection.source === connection.target) return false
      // connection.source = parent node (React Flow source), connection.target = child node
      // Check if child -> parent would create a cycle
      return !wouldCreateCycle(graphData, connection.target, connection.source)
    },
    [graphData],
  )

  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!graphData || mutating) return
      if (!user) return
      if (!connection.source || !connection.target) return

      // connection.source = parent (React Flow source), connection.target = child (React Flow target)
      const childId = connection.target
      const parentId = connection.source

      setMutating(true)
      setEditError(null)
      try {
        // Get current label data to preserve names and add new parent
        const childLabel = await fetchLabel(childId)
        const newParents = [...new Set([...childLabel.parents, parentId])]
        await updateLabel(childId, { names: childLabel.names, parents: newParents })
        // Refetch graph
        const newGraphData = await fetchLabelGraph()
        setGraphData(newGraphData)
      } catch {
        setEditError('Failed to add parent relationship.')
      } finally {
        setMutating(false)
      }
    },
    [graphData, user, mutating],
  )

  const onEdgeClick = useCallback(
    async (_: React.MouseEvent, edge: Edge) => {
      if (!graphData || !user || mutating) return

      // React Flow edge: source = parent, target = child
      const childId = edge.target
      const parentId = edge.source

      if (!window.confirm(`Remove parent #${parentId} from #${childId}?`)) return

      setMutating(true)
      setEditError(null)
      try {
        const childLabel = await fetchLabel(childId)
        const newParents = childLabel.parents.filter((p) => p !== parentId)
        await updateLabel(childId, { names: childLabel.names, parents: newParents })
        const newGraphData = await fetchLabelGraph()
        setGraphData(newGraphData)
      } catch {
        setEditError('Failed to remove parent relationship.')
      } finally {
        setMutating(false)
      }
    },
    [graphData, user, mutating],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24 animate-fade-in">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-24 animate-fade-in">
        <p className="font-display text-2xl text-muted italic">No labels yet</p>
        <p className="text-sm text-muted mt-2">Define labels in labels.toml to see the graph.</p>
      </div>
    )
  }

  return (
    <div className="animate-fade-in -mx-6 -my-10">
      {/* Header bar */}
      <div className="px-6 py-4 border-b border-border bg-paper flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <GitFork size={18} className="text-accent" />
          <h1 className="font-display text-2xl text-ink">Label Graph</h1>
          <span className="text-xs font-mono text-muted ml-2">
            {graphData.nodes.length} labels
          </span>
          {mutating && (
            <div className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          )}
          {editError && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-1.5 rounded-lg">
              {editError}
            </div>
          )}
        </div>

        {/* Search */}
        <div className="relative max-w-xs w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter labels..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-border rounded-lg
              bg-paper focus:outline-none focus:border-accent/50 transition-colors"
          />
        </div>
      </div>

      {/* Graph canvas */}
      <div style={{ height: 'calc(100vh - 200px)' }}>
        <ReactFlow
          nodes={filteredNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          isValidConnection={user ? isValidConnection : undefined}
          onConnect={user ? (conn) => void onConnect(conn) : undefined}
          onEdgeClick={user ? (e, edge) => void onEdgeClick(e, edge) : undefined}
          edgesReconnectable={!!user}
          connectOnClick={false}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={{ hideAttribution: true }}
          minZoom={0.3}
          maxZoom={2}
        >
          <Background color="#e0dbd4" gap={20} size={1} />
          <Controls
            className="!bg-paper !border-border !shadow-sm [&>button]:!bg-paper [&>button]:!border-border [&>button]:!text-muted [&>button:hover]:!bg-paper-warm"
          />
        </ReactFlow>
      </div>
    </div>
  )
}
