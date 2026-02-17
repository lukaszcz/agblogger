import { create } from 'zustand'
import type { SiteConfigResponse } from '@/api/client'
import api from '@/api/client'

interface SiteState {
  config: SiteConfigResponse | null
  isLoading: boolean
  fetchConfig: () => Promise<void>
}

export const useSiteStore = create<SiteState>((set) => ({
  config: null,
  isLoading: false,

  fetchConfig: async () => {
    set({ isLoading: true })
    try {
      const config = await api.get('pages').json<SiteConfigResponse>()
      set({ config, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },
}))
