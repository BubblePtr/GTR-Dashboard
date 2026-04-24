import { useTopicStats, useTopics, usePipelineRuns } from '../hooks/useApi'
import { CheckCircle, Clock, XCircle, Send, Zap } from 'lucide-react'

export default function Dashboard() {
  const { data: stats } = useTopicStats()
  const { data: topics } = useTopics('pending')
  const { data: runs } = usePipelineRuns()

  const statCards = [
    { label: '待审核', value: stats?.pending ?? 0, icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-50' },
    { label: '已采纳', value: stats?.approved ?? 0, icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50' },
    { label: '已发布', value: stats?.published ?? 0, icon: Send, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: '已跳过', value: stats?.skipped ?? 0, icon: XCircle, color: 'text-gray-600', bg: 'bg-gray-50' },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className={`${card.bg} rounded-lg p-4 border border-gray-100`}>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{card.label}</span>
              <card.icon size={20} className={card.color} />
            </div>
            <div className="text-2xl font-bold mt-2 text-gray-900">{card.value}</div>
          </div>
        ))}
      </div>

      {/* Latest pending topics */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">最新待审选题</h3>
          <span className="text-xs text-gray-500">前 5 条</span>
        </div>
        <div className="divide-y divide-gray-100">
          {topics?.slice(0, 5).map((topic) => (
            <div key={topic.id} className="px-4 py-3 flex items-center gap-4">
              <Zap size={16} className="text-yellow-500 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {topic.project_name || '未知项目'}
                  </div>
                  {topic.final_score !== null && topic.final_score !== undefined && (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium">
                      {topic.final_score.toFixed(1)}
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {topic.differentiation_angle || '暂无差异化角度'}
                </div>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600">
                {topic.engagement_estimate}
              </span>
            </div>
          ))}
          {(!topics || topics.length === 0) && (
            <div className="px-4 py-8 text-center text-sm text-gray-400">暂无待审选题</div>
          )}
        </div>
      </div>

      {/* Recent pipeline runs */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">最近 Pipeline 运行</h3>
        </div>
        <div className="divide-y divide-gray-100">
          {runs?.slice(0, 5).map((run) => (
            <div key={run.id} className="px-4 py-3 flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">Run #{run.id}</span>
                <span className="text-xs text-gray-500 ml-2">{run.triggered_by}</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{run.projects_collected} 项目</span>
                <span>{run.topics_generated} 选题</span>
                <StatusBadge status={run.status} />
              </div>
            </div>
          ))}
          {(!runs || runs.length === 0) && (
            <div className="px-4 py-8 text-center text-sm text-gray-400">暂无运行记录</div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    success: 'bg-green-100 text-green-700',
    partial_failure: 'bg-yellow-100 text-yellow-700',
    failed: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-600'}`}>
      {status === 'success' ? '成功' : status === 'running' ? '运行中' : status === 'failed' ? '失败' : '部分失败'}
    </span>
  )
}