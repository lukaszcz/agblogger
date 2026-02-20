import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { fetchLabels, createLabel } from '@/api/labels'
import type { LabelResponse } from '@/api/client'

vi.mock('@/api/labels', () => ({
  fetchLabels: vi.fn(),
  createLabel: vi.fn(),
}))

import LabelInput from '../LabelInput'

const mockFetchLabels = vi.mocked(fetchLabels)
const mockCreateLabel = vi.mocked(createLabel)

const sampleLabels: LabelResponse[] = [
  { id: 'swe', names: ['software engineering'], is_implicit: false, parents: [], children: [], post_count: 3 },
  { id: 'math', names: ['mathematics'], is_implicit: false, parents: [], children: [], post_count: 1 },
]

describe('LabelInput', () => {
  beforeEach(() => {
    mockFetchLabels.mockReset()
    mockCreateLabel.mockReset()
  })

  it('clears loadError after a successful fetch', async () => {
    // First fetch fails
    mockFetchLabels.mockRejectedValueOnce(new Error('Network error'))

    const onChange = vi.fn()
    const { rerender } = render(<LabelInput value={[]} onChange={onChange} />)

    // Error message should appear
    await waitFor(() => {
      expect(screen.getByText('Failed to load labels. Type to create new ones.')).toBeInTheDocument()
    })

    // Now simulate a successful fetch on re-render by re-mounting
    mockFetchLabels.mockResolvedValueOnce(sampleLabels)
    rerender(<LabelInput value={[]} onChange={onChange} key="retry" />)

    // Error message should disappear after successful load
    await waitFor(() => {
      expect(
        screen.queryByText('Failed to load labels. Type to create new ones.'),
      ).not.toBeInTheDocument()
    })
  })

  it('clears loadError after a successful label create', async () => {
    const user = userEvent.setup()
    // Initial fetch fails
    mockFetchLabels.mockRejectedValueOnce(new Error('Network error'))

    const onChange = vi.fn()
    render(<LabelInput value={[]} onChange={onChange} />)

    // Error message should appear
    await waitFor(() => {
      expect(screen.getByText('Failed to load labels. Type to create new ones.')).toBeInTheDocument()
    })

    // Type a new label name and create it
    const newLabel: LabelResponse = {
      id: 'newlabel',
      names: ['newlabel'],
      is_implicit: false,
      parents: [],
      children: [],
      post_count: 0,
    }
    mockCreateLabel.mockResolvedValueOnce(newLabel)

    const input = screen.getByRole('combobox')
    await user.type(input, 'newlabel')
    await user.keyboard('{Enter}')

    // Error message should be cleared after successful create
    await waitFor(() => {
      expect(
        screen.queryByText('Failed to load labels. Type to create new ones.'),
      ).not.toBeInTheDocument()
    })
  })
})
