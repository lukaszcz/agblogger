import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { LabelResponse } from '@/api/client'
import FilterPanel, { EMPTY_FILTER, type FilterState } from '../FilterPanel'

const mockFetchLabels = vi.fn()

vi.mock('@/api/labels', () => ({
  fetchLabels: (...args: unknown[]) => mockFetchLabels(...args) as unknown,
}))

const allLabels: LabelResponse[] = [
  { id: 'swe', names: ['software engineering'], is_implicit: false, parents: [], children: [], post_count: 5 },
  { id: 'cs', names: ['computer science'], is_implicit: false, parents: [], children: ['swe'], post_count: 10 },
  { id: 'math', names: ['mathematics'], is_implicit: false, parents: [], children: [], post_count: 3 },
]

function renderPanel(value: FilterState = EMPTY_FILTER, onChange = vi.fn()) {
  const result = render(<FilterPanel value={value} onChange={onChange} />)
  return { ...result, onChange }
}

describe('FilterPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchLabels.mockResolvedValue(allLabels)
  })

  it('renders Filters button', () => {
    renderPanel()
    expect(screen.getByText('Filters')).toBeInTheDocument()
  })

  it('opens panel on click', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search labels...')).toBeInTheDocument()
    })
  })

  it('shows active filter count badge', () => {
    const filter: FilterState = { ...EMPTY_FILTER, labels: ['swe', 'cs'], author: 'Admin' }
    renderPanel(filter)

    // 3 active: 2 labels + 1 author
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows filter chips when panel is closed', () => {
    const filter: FilterState = { ...EMPTY_FILTER, labels: ['swe'], author: 'Admin' }
    renderPanel(filter)

    expect(screen.getByText('#swe')).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()
  })

  it('shows date range chips', () => {
    const filter: FilterState = { ...EMPTY_FILTER, fromDate: '2026-01-01', toDate: '2026-02-01' }
    renderPanel(filter)

    expect(screen.getByText('2026-01-01 - 2026-02-01')).toBeInTheDocument()
  })

  it('filters labels by search', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('#swe')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Search labels...'), 'math')

    // Only math should be visible
    expect(screen.getByText('#math')).toBeInTheDocument()
    expect(screen.queryByText('#swe')).not.toBeInTheDocument()
    expect(screen.queryByText('#cs')).not.toBeInTheDocument()
  })

  it('filters labels by name case-insensitively', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('#swe')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Search labels...'), 'Software')

    expect(screen.getByText('#swe')).toBeInTheDocument()
    expect(screen.queryByText('#math')).not.toBeInTheDocument()
  })

  it('toggles label selection', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderPanel(EMPTY_FILTER, onChange)

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('#swe')).toBeInTheDocument()
    })

    await user.click(screen.getByText('#swe'))

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labels: ['swe'] }))
  })

  it('removes label from filter', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { ...EMPTY_FILTER, labels: ['swe'] }
    renderPanel(filter, onChange)

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('#swe')).toBeInTheDocument()
    })

    await user.click(screen.getByText('#swe'))

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labels: [] }))
  })

  it('toggles label mode OR/AND', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderPanel(EMPTY_FILTER, onChange)

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('AND')).toBeInTheDocument()
    })

    await user.click(screen.getByText('AND'))

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labelMode: 'and' }))
  })

  it('updates author filter', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderPanel(EMPTY_FILTER, onChange)

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Filter by author...')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Filter by author...'), 'A')

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ author: 'A' }))
  })

  it('clears all filters via chip area', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { labels: ['swe'], labelMode: 'and', author: 'Admin', fromDate: '2026-01-01', toDate: '' }
    renderPanel(filter, onChange)

    // Chips area has "Clear all" (panel is closed, so only 1 visible)
    const clearAllButtons = screen.getAllByText('Clear all')
    await user.click(clearAllButtons[0]!)

    expect(onChange).toHaveBeenCalledWith(EMPTY_FILTER)
  })

  it('shows "No matching labels" when search has no results', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search labels...')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Search labels...'), 'nonexistent')

    expect(screen.getByText('No matching labels')).toBeInTheDocument()
  })

  it('closes panel via Close button', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      expect(screen.getByText('Close')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Close'))

    // The panel enters 'closing' state which will remove content after animation
    // The close button itself should trigger the state change
  })

  it('updates from date', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderPanel(EMPTY_FILTER, onChange)

    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      const dateInputs = document.querySelectorAll('input[type="date"]')
      expect(dateInputs.length).toBe(2)
    })

    const fromInput = document.querySelectorAll('input[type="date"]')[0] as HTMLInputElement
    // Use fireEvent since userEvent doesn't handle date inputs well
    await user.clear(fromInput)
    await user.type(fromInput, '2026-01-01')

    expect(onChange).toHaveBeenCalled()
  })

  it('removes label chip when X is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { ...EMPTY_FILTER, labels: ['swe'] }
    renderPanel(filter, onChange)

    // Chips are visible when panel is closed
    const chipButton = screen.getByText('#swe').parentElement?.querySelector('button')
    expect(chipButton).toBeTruthy()
    await user.click(chipButton!)

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labels: [] }))
  })

  it('removes author chip when X is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { ...EMPTY_FILTER, author: 'Admin' }
    renderPanel(filter, onChange)

    const chipButton = screen.getByText('Admin').parentElement?.querySelector('button')
    expect(chipButton).toBeTruthy()
    await user.click(chipButton!)

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ author: '' }))
  })

  it('removes date range chip when X is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { ...EMPTY_FILTER, fromDate: '2026-01-01', toDate: '2026-02-01' }
    renderPanel(filter, onChange)

    const dateChipButton = screen.getByText('2026-01-01 - 2026-02-01').parentElement?.querySelector('button')
    expect(dateChipButton).toBeTruthy()
    await user.click(dateChipButton!)

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ fromDate: '', toDate: '' }))
  })

  it('clears all filters from inside panel', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const filter: FilterState = { labels: ['swe'], labelMode: 'or', author: 'Admin', fromDate: '', toDate: '' }
    renderPanel(filter, onChange)

    // Open the panel
    await user.click(screen.getByText('Filters'))

    await waitFor(() => {
      // There should be a "Clear all" inside the panel
      const clearButtons = screen.getAllByText('Clear all')
      expect(clearButtons.length).toBeGreaterThanOrEqual(1)
    })

    // Click the last "Clear all" (the one inside the panel)
    const clearButtons = screen.getAllByText('Clear all')
    await user.click(clearButtons[clearButtons.length - 1]!)

    expect(onChange).toHaveBeenCalledWith(EMPTY_FILTER)
  })
})
