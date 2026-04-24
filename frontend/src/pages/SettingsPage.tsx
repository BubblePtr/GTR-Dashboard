import { usePreferences, useUpdatePreferences, useWeights, useUpdateWeights } from '../hooks/useApi'

export default function SettingsPage() {
  const { data: prefs } = usePreferences()
  const updatePrefs = useUpdatePreferences()
  const { data: weights } = useWeights()
  const updateWeights = useUpdateWeights()

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-bold text-gray-900">设置</h2>

      {/* Preferences */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
        <h3 className="font-semibold text-gray-900">用户偏好</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">定位</label>
            <input
              type="text"
              defaultValue={prefs?.positioning || ''}
              onBlur={(e) => updatePrefs.mutate({ positioning: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">偏好语言</label>
            <input
              type="text"
              defaultValue={prefs?.preferred_languages || ''}
              onBlur={(e) => updatePrefs.mutate({ preferred_languages: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">最低星标数</label>
            <input
              type="number"
              defaultValue={prefs?.min_stars_threshold || 100}
              onBlur={(e) => updatePrefs.mutate({ min_stars_threshold: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">本地AI权重</label>
            <input
              type="number"
              step={0.05}
              min={0}
              max={1}
              defaultValue={prefs?.local_ai_weight || 0.3}
              onBlur={(e) => updatePrefs.mutate({ local_ai_weight: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">每日运行时间</label>
            <input
              type="time"
              defaultValue={prefs?.daily_run_time || '09:00'}
              onBlur={(e) => updatePrefs.mutate({ daily_run_time: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              defaultChecked={prefs?.auto_publish || false}
              onChange={(e) => updatePrefs.mutate({ auto_publish: e.target.checked })}
              className="rounded border-gray-300"
            />
            <label className="text-sm text-gray-700">自动发布</label>
          </div>
        </div>
      </div>

      {/* Scoring Weights */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
        <h3 className="font-semibold text-gray-900">评分权重</h3>
        <div className="space-y-4">
          {weights && (
            <>
              <WeightSlider
                label="新颖度"
                value={weights.novelty_weight}
                onChange={(v) => updateWeights.mutate({ novelty_weight: v })}
              />
              <WeightSlider
                label="实用性"
                value={weights.utility_weight}
                onChange={(v) => updateWeights.mutate({ utility_weight: v })}
              />
              <WeightSlider
                label="本地AI相关性"
                value={weights.local_ai_weight}
                onChange={(v) => updateWeights.mutate({ local_ai_weight: v })}
              />
              <WeightSlider
                label="文档质量"
                value={weights.doc_quality_weight}
                onChange={(v) => updateWeights.mutate({ doc_quality_weight: v })}
              />
              <WeightSlider
                label="互动潜力"
                value={weights.engagement_weight}
                onChange={(v) => updateWeights.mutate({ engagement_weight: v })}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function WeightSlider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm text-gray-500">{(value * 100).toFixed(0)}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
    </div>
  )
}
