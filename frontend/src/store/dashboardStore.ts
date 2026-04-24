import { create } from 'zustand'

interface DashboardState {
  sidebarOpen: boolean
  activePipelineRunId: number | null
  setSidebarOpen: (open: boolean) => void
  setActivePipelineRunId: (id: number | null) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  sidebarOpen: true,
  activePipelineRunId: null,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActivePipelineRunId: (id) => set({ activePipelineRunId: id }),
}))