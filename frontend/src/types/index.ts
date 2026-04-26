export interface Topic {
  id: number
  candidate_id: number | null
  profile_id: number | null
  project_name: string | null
  github_url: string | null
  why_post: string | null
  differentiation_angle: string | null
  target_audience: string | null
  engagement_estimate: string
  draft_tweet: string | null
  draft_script: string | null
  draft_outline: string | null
  user_edited_draft_tweet: string | null
  user_edited_draft_script: string | null
  user_edited_draft_outline: string | null
  review_notes: string | null
  priority_score: number | null
  final_score: number | null
  generation_status: string
  created_at: string
  action: string
  review_state: string
  message_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  seen_count: number
  latest_topic_id: number | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface TopicChatResponse {
  response: string
  action: string | null
  refined_content: string | null
  signals: ReviewSignal[]
}

export interface ReviewMessage {
  id: number
  topic_id: number
  candidate_id?: number | null
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ReviewSignal {
  id?: number
  topic_id?: number
  candidate_id?: number | null
  message_id?: number | null
  signal_type: string
  label: string
  polarity: string
  strength: number
  created_at?: string
}

export interface TopicReviewSession {
  topic: Topic
  messages: ReviewMessage[]
  signals: ReviewSignal[]
}

export interface TopicStats {
  pending: number
  approved: number
  published: number
  skipped: number
  total: number
}

export interface PipelineRun {
  id: number
  status: string
  projects_collected: number
  projects_analyzed: number
  topics_generated: number
  triggered_by: string
  started_at: string
  finished_at: string | null
  stages: PipelineStage[]
  error_log: string | null
}

export interface PipelineStage {
  id: number
  stage_name: string
  status: string
  progress: number
  message: string | null
  started_at: string
  finished_at: string | null
}

export interface Preference {
  id: number
  positioning: string | null
  preferred_languages: string | null
  min_stars_threshold: number
  local_ai_weight: number
  daily_run_time: string
  auto_publish: boolean
  updated_at: string
}

export interface Weight {
  id: number
  novelty_weight: number
  utility_weight: number
  local_ai_weight: number
  doc_quality_weight: number
  engagement_weight: number
  updated_at: string
}

export interface HistoryPoint {
  date: string
  avg_score: number
  total_projects: number
  total_selected: number
}
