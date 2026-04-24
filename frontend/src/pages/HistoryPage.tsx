import { useHistory } from '../hooks/useApi'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

export default function HistoryPage() {
  const { data: history } = useHistory()

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">历史对比</h2>

      {/* Score trend */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-4">平均评分趋势</h3>
        <div className="h-64">
          {history && history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 10]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg_score"
                  name="平均评分"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              暂无历史数据
            </div>
          )}
        </div>
      </div>

      {/* Volume trend */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-4">项目数量趋势</h3>
        <div className="h-64">
          {history && history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total_projects"
                  name="分析项目"
                  stroke="#059669"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="total_selected"
                  name="入选选题"
                  stroke="#d97706"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              暂无历史数据
            </div>
          )}
        </div>
      </div>

      {/* Data table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">历史数据</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 text-left">日期</th>
                <th className="px-4 py-2 text-right">平均评分</th>
                <th className="px-4 py-2 text-right">分析项目</th>
                <th className="px-4 py-2 text-right">入选选题</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {history?.map((row) => (
                <tr key={row.date} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{row.date}</td>
                  <td className="px-4 py-2 text-right">{row.avg_score}</td>
                  <td className="px-4 py-2 text-right">{row.total_projects}</td>
                  <td className="px-4 py-2 text-right">{row.total_selected}</td>
                </tr>
              ))}
              {(!history || history.length === 0) && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                    暂无历史数据
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
