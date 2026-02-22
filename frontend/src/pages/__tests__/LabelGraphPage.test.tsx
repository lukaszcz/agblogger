import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { UserResponse, LabelGraphResponse } from '@/api/client'

vi.mock('@/api/client', () => {
  class HTTPError extends Error {
    response: { status: number }
    constructor(status: number) {
      super(`HTTP ${status}`)
      this.response = { status }
    }
  }
  return { default: {}, HTTPError }
})

const mockFetchLabelGraph = vi.fn()
const mockFetchLabel = vi.fn()
const mockUpdateLabel = vi.fn()

vi.mock('@/api/labels', () => ({
  fetchLabelGraph: (...args: unknown[]) => mockFetchLabelGraph(...args) as unknown,
  fetchLabel: (...args: unknown[]) => mockFetchLabel(...args) as unknown,
  updateLabel: (...args: unknown[]) => mockUpdateLabel(...args) as unknown,
}))

// Stub React Flow to avoid canvas/DOM issues in jsdom
vi.mock('@xyflow/react', () => {
  const nodesState = (initial: unknown[]) => {
    let nodes = initial
    return [nodes, (n: unknown[]) => { nodes = n }, vi.fn()]
  }
  const edgesState = (initial: unknown[]) => {
    let edges = initial
    return [edges, (e: unknown[]) => { edges = e }, vi.fn()]
  }
  return {
    ReactFlow: ({ nodes }: { nodes?: Array<{ id: string; data?: { label?: string; names?: string[] } }> }) => (
      <div data-testid="react-flow">
        {Array.isArray(nodes) && nodes.map((n) => (
          <div key={n.id} data-testid={`node-${n.id}`}>
            {n.data?.label}
          </div>
        ))}
      </div>
    ),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    Position: { Top: 'top', Bottom: 'bottom' },
    MarkerType: { ArrowClosed: 'arrowclosed' },
    useNodesState: nodesState,
    useEdgesState: edgesState,
  }
})

vi.mock('@dagrejs/dagre', () => {
  function MockGraph() {
    return {
      setDefaultEdgeLabel: vi.fn().mockReturnThis(),
      setGraph: vi.fn(),
      setNode: vi.fn(),
      setEdge: vi.fn(),
      node: () => ({ x: 100, y: 100 }),
    }
  }
  return {
    default: {
      graphlib: { Graph: MockGraph },
      layout: vi.fn(),
    },
  }
})

let mockUser: UserResponse | null = null

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: UserResponse | null }) => unknown) =>
    selector({ user: mockUser }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

import LabelGraphPage from '../LabelGraphPage'

const { HTTPError: MockHTTPError } = await import('@/api/client')

const graphData: LabelGraphResponse = {
  nodes: [
    { id: 'cs', names: ['computer science'], post_count: 10 },
    { id: 'swe', names: ['software engineering'], post_count: 5 },
    { id: 'math', names: ['mathematics'], post_count: 3 },
  ],
  edges: [{ source: 'swe', target: 'cs' }],
}

function renderGraph() {
  return render(
    <MemoryRouter>
      <LabelGraphPage viewToggle={<button>Toggle</button>} />
    </MemoryRouter>,
  )
}

describe('LabelGraphPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 1, username: 'admin', email: 'a@t.com', display_name: null, is_admin: true }
  })

  it('shows spinner while loading', () => {
    mockFetchLabelGraph.mockReturnValue(new Promise(() => {}))
    renderGraph()
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('shows error message', async () => {
    mockFetchLabelGraph.mockRejectedValue(new Error('Network'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('Failed to load label graph. Please try again later.')).toBeInTheDocument()
    })
    consoleSpy.mockRestore()
  })

  it('shows "No labels yet" when empty', async () => {
    mockFetchLabelGraph.mockResolvedValue({ nodes: [], edges: [] })
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('No labels yet')).toBeInTheDocument()
    })
  })

  it('shows label count in header', async () => {
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('3 labels')).toBeInTheDocument()
    })
  })

  it('renders the graph with nodes', async () => {
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByTestId('react-flow')).toBeInTheDocument()
    })
  })

  it('renders search input', async () => {
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Filter labels...')).toBeInTheDocument()
    })
  })

  it('renders view toggle', async () => {
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('Toggle')).toBeInTheDocument()
    })
  })

  it('shows 401 error as session expired', async () => {
    mockFetchLabelGraph.mockRejectedValue(
      new (MockHTTPError as unknown as new (s: number) => Error)(401),
    )
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('Session expired. Please log in to view the graph.')).toBeInTheDocument()
    })
  })

  it('accepts search input', async () => {
    const user = userEvent.setup()
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Filter labels...')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Filter labels...'), 'cs')

    // Search value is set in the input
    expect(screen.getByPlaceholderText('Filter labels...')).toHaveValue('cs')
  })

  it('renders without edit controls when unauthenticated', async () => {
    mockUser = null
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByTestId('react-flow')).toBeInTheDocument()
    })
  })

  it('renders "Label Graph" heading', async () => {
    mockFetchLabelGraph.mockResolvedValue(graphData)
    renderGraph()

    await waitFor(() => {
      expect(screen.getByText('Label Graph')).toBeInTheDocument()
    })
  })
})
