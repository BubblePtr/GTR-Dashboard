import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import TopicsPage from './pages/TopicsPage'
import PipelinePage from './pages/PipelinePage'
import SettingsPage from './pages/SettingsPage'
import HistoryPage from './pages/HistoryPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/topics" element={<TopicsPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}
