import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiGet = vi.fn()

vi.mock('@/api/client', () => ({
  default: { get: () => ({ json: () => mockApiGet() as unknown }) },
}))

const { useSiteStore } = await import('@/stores/siteStore')

describe('siteStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useSiteStore.setState({ config: null, isLoading: false, error: null })
  })

  it('has correct initial state', () => {
    const state = useSiteStore.getState()
    expect(state.config).toBeNull()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchConfig sets config on success', async () => {
    const config = { title: 'Test', description: 'Blog', pages: [] }
    mockApiGet.mockResolvedValue(config)

    await useSiteStore.getState().fetchConfig()

    const state = useSiteStore.getState()
    expect(state.config).toEqual(config)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchConfig sets error on failure', async () => {
    mockApiGet.mockRejectedValue(new Error('Network'))

    await useSiteStore.getState().fetchConfig()

    const state = useSiteStore.getState()
    expect(state.config).toBeNull()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBe('Failed to load site configuration')
  })

  it('fetchConfig sets isLoading during fetch', async () => {
    let resolvePromise: (v: unknown) => void
    mockApiGet.mockReturnValue(new Promise((r) => { resolvePromise = r }))

    const promise = useSiteStore.getState().fetchConfig()

    expect(useSiteStore.getState().isLoading).toBe(true)

    resolvePromise!({ title: 'T', description: '', pages: [] })
    await promise

    expect(useSiteStore.getState().isLoading).toBe(false)
  })
})
