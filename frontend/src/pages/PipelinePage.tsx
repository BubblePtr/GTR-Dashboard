import { useState } from 'react'
import { useTriggerPipeline, usePipelineRun, usePipelineRuns } from '../hooks/useApi'
import { useDashboardStore } from '../store/dashboardStore'
import { Play, Loader2, CheckCircle, XCircle } from 'lucide-react'

export default function PipelinePage() {
  const [config, setConfig] = useState({
    languages: '',
    limit: 10,
    source: 'legacy',
    model: 'qwen3.6-max-preview',
  })

  const trigger = useTriggerPipeline()
  const { activePipelineRunId, setActivePipelineRunId } = useDashboardStore()
  const { data: activeRun } = usePipelineRun(activePipelineRunId)
  const { data: runs } = usePipelineRuns()

  const handleRun = () => {
    const langs = config.languages
      ? config.languages.split(',').map((s) => s.trim()).filter(Boolean)
      : ['']
    trigger.mutate(
      {
        languages: langs,
        limit: config.limit,
        source: config.source,
        model: config.model,
      },
      {
        onSuccess: (data) => {
          setActivePipelineRunId(data.run_id)
        },
      }
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Pipeline</h2>

      {/* Config form */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
        <h3 className="font-semibold text-gray-900">运行配置</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">语言（逗号分隔）</label>
            <input
              type="text"
              value={config.languages}
              placeholder="留空=全语言最热，逗号分隔如 python,go"
              onChange={(e) => setConfig({ ...config, languages: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">数量限制</label>
            <input
              type="number"
              value={config.limit}
              min={1}
              max={50}
              onChange={(e) => setConfig({ ...config, limit: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">数据源</label>
            <select
              value={config.source}
              onChange={(e) => setConfig({ ...config, source: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="tavily">Tavily</option>
              <option value="exa">Exa</option>
              <option value="both">Both</option>
              <option value="legacy">Legacy (GitHub Trending)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">模型</label>
            <input
              type="text"
              value={config.model}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={trigger.isPending || activeRun?.status === 'running'}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {trigger.isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {activeRun?.status === 'running' ? '运行中...' : '启动 Pipeline'}
        </button>
      </div>

      {/* Active run progress */}
      {activeRun && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">运行进度 #{activeRun.id}</h3>
            <StatusBadge status={activeRun.status} />
          </div>
          <div className="space-y-2">
            {activeRun.stages.map((stage) => (
              <div key={stage.id} className="flex items-center gap-3">
                <StageIcon status={stage.status} />
                <div className="flex-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize">{stage.stage_name}</span>
                    <span className="text-xs text-gray-500">{stage.progress}%</span>
                  </div>
                  <div className="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        stage.status === 'complete'
                          ? 'bg-green-500'
                          : stage.status === 'failed'
                          ? 'bg-red-500'
                          : 'bg-blue-500'
                      }`}
                      style={{ width: `${stage.progress}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
          {activeRun.error_log && (
            <div className="mt-3 p-2 bg-red-50 text-red-700 text-xs rounded">
              {activeRun.error_log}
            </div>
          )}
        </div>
      )}

      {/* History */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">历史运行</h3>
        </div>
        <div className="divide-y divide-gray-100">
          {runs?.map((run) => (
            <div
              key={run.id}
              className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-50"
              onClick={() => setActivePipelineRunId(run.id)}
            >
              <div className="flex items-center gap-3">
                <StatusBadge status={run.status} />
                <span className="text-sm font-medium">Run #{run.id}</span>
                <span className="text-xs text-gray-500">{run.triggered_by}</span>
              </div>
              <div className="text-xs text-gray-500">
                {run.projects_collected} 项目 / {run.topics_generated} 选题
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

function StageIcon({ status }: { status: string }) {
  if (status === 'complete') return <CheckCircle size={16} className="text-green-500" />
  if (status === 'failed') return <XCircle size={16} className="text-red-500" />
  return <Loader2 size={16} className="text-blue-500 animate-spin" />
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