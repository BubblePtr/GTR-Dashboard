import { useState, useMemo } from 'react'
import { useTopics } from '../hooks/useApi'
import { ArrowUpDown, MessageSquare } from 'lucide-react'
import type { Topic } from '../types'
import TopicReviewPanel from '../components/TopicReviewPanel'

const tabs = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已采纳' },
  { key: 'published', label: '已发布' },
  { key: 'skipped', label: '已跳过' },
]

const sortOptions = [
  { key: 'score_desc', label: '评分（高→低）' },
  { key: 'score_asc', label: '评分（低→高）' },
  { key: 'engagement_desc', label: '互动度（高→低）' },
  { key: 'time_desc', label: '时间（新→旧）' },
  { key: 'time_asc', label: '时间（旧→新）' },
]

function sortTopics(topics: Topic[], sortKey: string): Topic[] {
  const engagementRank: Record<string, number> = { high: 3, medium: 2, low: 1 }
  const copy = [...topics]
  switch (sortKey) {
    case 'score_desc':
      return copy.sort((a, b) => (b.final_score ?? 0) - (a.final_score ?? 0))
    case 'score_asc':
      return copy.sort((a, b) => (a.final_score ?? 0) - (b.final_score ?? 0))
    case 'engagement_desc':
      return copy.sort((a, b) => (engagementRank[b.engagement_estimate] ?? 0) - (engagementRank[a.engagement_estimate] ?? 0))
    case 'time_desc':
      return copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    case 'time_asc':
      return copy.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    default:
      return copy
  }
}

const actionBadgeMap: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '待审核', color: 'text-yellow-700', bg: 'bg-yellow-50' },
  approved: { label: '已采纳', color: 'text-green-700', bg: 'bg-green-50' },
  published: { label: '已发布', color: 'text-blue-700', bg: 'bg-blue-50' },
  skipped: { label: '已跳过', color: 'text-gray-700', bg: 'bg-gray-50' },
}

export default function TopicsPage() {
  const [activeTab, setActiveTab] = useState('pending')
  const [sortKey, setSortKey] = useState('score_desc')
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const { data: topics, isLoading } = useTopics(activeTab)

  const sortedTopics = useMemo(() => {
    if (!topics) return []
    return sortTopics(topics, sortKey)
  }, [topics, sortKey])

  const handleReview = (topic: Topic) => {
    setSelectedTopic(topic)
    setIsPanelOpen(true)
  }

  const handleClosePanel = () => {
    setIsPanelOpen(false)
    setSelectedTopic(null)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">选题管理</h2>

      {/* Tabs + Sort */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <ArrowUpDown size={14} className="text-gray-400" />
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {sortOptions.map((opt) => (
              <option key={opt.key} value={opt.key}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Topic cards */}
      {isLoading && <div className="text-sm text-gray-500">加载中...</div>}
      <div className="space-y-3">
        {sortedTopics.map((topic) => (
          <div key={topic.id} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-gray-900">
                    {topic.project_name || '未知项目'}
                  </h3>
                  {topic.final_score !== null && topic.final_score !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium border border-orange-100">
                      评分: {topic.final_score.toFixed(1)}
                    </span>
                  )}
                  {topic.github_url && (
                    <a
                      href={topic.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline truncate max-w-xs"
                    >
                      {topic.github_url}
                    </a>
                  )}
                  {actionBadgeMap[topic.action] && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${actionBadgeMap[topic.action].bg} ${actionBadgeMap[topic.action].color} font-medium`}>
                      {actionBadgeMap[topic.action].label}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mb-2">{topic.why_post || '暂无选题理由'}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  {topic.differentiation_angle && (
                    <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded">差异化</span>
                  )}
                  {topic.target_audience && (
                    <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded">受众</span>
                  )}
                  <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded">
                    互动: {topic.engagement_estimate}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleReview(topic)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors flex-shrink-0"
              >
                <MessageSquare size={14} />
                审阅
              </button>
            </div>
          </div>
        ))}
        {sortedTopics.length === 0 && !isLoading && (
          <div className="text-center py-12 text-gray-400 text-sm">该状态下暂无选题</div>
        )}
      </div>

      <TopicReviewPanel
        topic={selectedTopic}
        isOpen={isPanelOpen}
        onClose={handleClosePanel}
      />
    </div>
  )
}
