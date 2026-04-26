import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Topic, TopicStats, PipelineRun, Preference, Weight, HistoryPoint, ChatMessage, TopicChatResponse, TopicReviewSession } from '../types'

export function useTopics(status?: string, date?: string) {
  return useQuery({
    queryKey: ['topics', status, date],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (status) params.append('status', status)
      if (date) params.append('date', date)
      const { data } = await api.get<Topic[]>(`/topics?${params}`)
      return data
    },
  })
}

export function useTodayTopics(limit = 8) {
  return useQuery({
    queryKey: ['todayTopics', limit],
    queryFn: async () => {
      const { data } = await api.get<Topic[]>(`/topics/today?limit=${limit}`)
      return data
    },
  })
}

export function useTopicPool(status?: string, limit = 50) {
  return useQuery({
    queryKey: ['topicPool', status, limit],
    queryFn: async () => {
      const params = new URLSearchParams({ scope: 'pool', limit: String(limit) })
      if (status) params.append('status', status)
      const { data } = await api.get<Topic[]>(`/topics?${params}`)
      return data
    },
  })
}

export function useTopicReviewSession(topicId: number | null) {
  return useQuery({
    queryKey: ['topicReview', topicId],
    queryFn: async () => {
      if (!topicId) return null
      const { data } = await api.get<TopicReviewSession>(`/topics/${topicId}/review`)
      return data
    },
    enabled: !!topicId,
  })
}

export function useTopicStats() {
  return useQuery({
    queryKey: ['topicStats'],
    queryFn: async () => {
      const { data } = await api.get<TopicStats>('/topics/stats')
      return data
    },
  })
}

export function useUpdateTopicAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ topicId, action, notes }: { topicId: number; action: string; notes?: string }) => {
      const { data } = await api.patch(`/topics/${topicId}/action`, { action, notes })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      qc.invalidateQueries({ queryKey: ['todayTopics'] })
      qc.invalidateQueries({ queryKey: ['topicPool'] })
      qc.invalidateQueries({ queryKey: ['topicStats'] })
    },
  })
}

export function useTopicChat() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ topicId, message, history }: { topicId: number; message: string; history: ChatMessage[] }) => {
      const { data } = await api.post<TopicChatResponse>(`/topics/${topicId}/chat`, { message, history })
      return data
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['topicReview', variables.topicId] })
      qc.invalidateQueries({ queryKey: ['todayTopics'] })
      qc.invalidateQueries({ queryKey: ['topicPool'] })
    },
  })
}

export function useUpdateTopicContent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ topicId, content }: { topicId: number; content: Record<string, string | null> }) => {
      const { data } = await api.patch(`/topics/${topicId}/content`, content)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
    },
  })
}

export function usePipelineRun(runId: number | null) {
  return useQuery({
    queryKey: ['pipeline', runId],
    queryFn: async () => {
      if (!runId) return null
      const { data } = await api.get<PipelineRun>(`/pipeline/status/${runId}`)
      return data
    },
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as PipelineRun | null
      return data?.status === 'running' ? 2000 : false
    },
  })
}

export function usePipelineRuns() {
  return useQuery({
    queryKey: ['pipelineRuns'],
    queryFn: async () => {
      const { data } = await api.get<PipelineRun[]>('/pipeline/runs')
      return data
    },
  })
}

export function useTriggerPipeline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (config: Record<string, unknown>) => {
      const { data } = await api.post<{ run_id: number; status: string }>('/pipeline/run', config)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipelineRuns'] })
      qc.invalidateQueries({ queryKey: ['todayTopics'] })
      qc.invalidateQueries({ queryKey: ['topicPool'] })
    },
  })
}

export function usePreferences() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: async () => {
      const { data } = await api.get<Preference>('/preferences')
      return data
    },
  })
}

export function useUpdatePreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (prefs: Partial<Preference>) => {
      const { data } = await api.put<Preference>('/preferences', prefs)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['preferences'] })
    },
  })
}

export function useWeights() {
  return useQuery({
    queryKey: ['weights'],
    queryFn: async () => {
      const { data } = await api.get<Weight>('/weights')
      return data
    },
  })
}

export function useUpdateWeights() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (weights: Partial<Weight>) => {
      const { data } = await api.put<Weight>('/weights', weights)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weights'] })
    },
  })
}

export function useHistory() {
  return useQuery({
    queryKey: ['history'],
    queryFn: async () => {
      const { data } = await api.get<HistoryPoint[]>('/history')
      return data
    },
  })
}
