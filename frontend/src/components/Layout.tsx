import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ListChecks, PlayCircle, Settings, History, Menu, X } from 'lucide-react'
import { useDashboardStore } from '../store/dashboardStore'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/topics', label: '选题管理', icon: ListChecks },
  { to: '/pipeline', label: 'Pipeline', icon: PlayCircle },
  { to: '/history', label: '历史对比', icon: History },
  { to: '/settings', label: '设置', icon: Settings },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen, setSidebarOpen } = useDashboardStore()

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-56' : 'w-0'
        } transition-all duration-200 bg-white border-r border-gray-200 flex-shrink-0 overflow-hidden`}
      >
        <div className="p-4">
          <h1 className="text-lg font-bold text-gray-900 mb-6">GTR Dashboard</h1>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`
                }
              >
                <item.icon size={18} />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-600"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="text-sm text-gray-500">本地AI实战派选题工作台</span>
        </header>
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  )
}