import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ListChecks, PanelLeftClose, PanelLeftOpen, PlayCircle, Settings } from 'lucide-react'
import { useDashboardStore } from '../store/dashboardStore'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/topics', label: '选题管理', icon: ListChecks },
  { to: '/pipeline', label: 'Pipeline', icon: PlayCircle },
  { to: '/settings', label: '设置', icon: Settings },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen, setSidebarOpen } = useDashboardStore()

  return (
    <div className="flex h-screen bg-gray-50">
      <aside
        className={`${
          sidebarOpen ? 'w-44' : 'w-14'
        } transition-all duration-200 bg-white border-r border-gray-200 flex-shrink-0 overflow-hidden`}
      >
        <div className="p-3">
          <div
            className={`mb-6 flex items-center gap-2 ${
              sidebarOpen ? 'justify-between' : 'justify-center'
            }`}
          >
            {sidebarOpen ? (
              <h1 className="truncate text-base font-bold text-gray-900">GTR</h1>
            ) : null}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="h-8 w-8 shrink-0 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-900 flex items-center justify-center"
              aria-label={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
              title={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
            >
              {sidebarOpen ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
            </button>
          </div>
          <nav className={`space-y-1 ${sidebarOpen ? '' : 'flex flex-col items-center'}`}>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                title={item.label}
                className={({ isActive }) => {
                  const state = isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                  const base = 'rounded-md text-sm font-medium transition-colors'

                  return sidebarOpen
                    ? `flex w-full items-center gap-3 px-2.5 py-2 ${base} ${state}`
                    : `flex h-8 w-8 items-center justify-center ${base} ${state}`
                }}
              >
                <item.icon size={18} className="shrink-0" />
                {sidebarOpen && <span className="truncate">{item.label}</span>}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 overflow-auto p-5">{children}</main>
      </div>
    </div>
  )
}
