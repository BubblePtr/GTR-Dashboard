import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bot,
  CheckCircle,
  Clock,
  Loader2,
  Play,
  PanelRightClose,
  PanelRightOpen,
  Send,
  UserRound,
  XCircle,
} from 'lucide-react'
import {
  useTodayTopics,
  useTopicPool,
  useTopicChat,
  useTopicReviewSession,
  useTriggerPipeline,
  useUpdateTopicAction,
} from '../hooks/useApi'
import { useDashboardStore } from '../store/dashboardStore'
import type { ChatMessage, ReviewSignal, Topic } from '../types'

const stateStyles: Record<string, string> = {
  未聊: 'bg-gray-100 text-gray-600',
  对话中: 'bg-blue-50 text-blue-700',
  已采纳: 'bg-green-50 text-green-700',
  已跳过: 'bg-gray-100 text-gray-500',
}

const signalTypeLabel: Record<string, string> = {
  preference: '偏好',
  concern: '顾虑',
  requirement: '要求',
  adoption_reason: '采纳理由',
  rejection_reason: '跳过理由',
}

const poolFilters = [
  { label: '待聊', value: 'pending' },
  { label: '对话中', value: 'chatting' },
  { label: '已采纳', value: 'approved' },
  { label: '已跳过', value: 'skipped' },
]

export default function TopicsPage() {
  const { data: candidates, isLoading } = useTodayTopics(8)
  const [candidateView, setCandidateView] = useState<'today' | 'pool'>('today')
  const [poolStatus, setPoolStatus] = useState<string | undefined>(undefined)
  const { data: poolCandidates, isLoading: isPoolLoading } = useTopicPool(poolStatus, 50)
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [decisionNote, setDecisionNote] = useState('')
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([])
  const [chatError, setChatError] = useState<string | null>(null)
  const [contextOpen, setContextOpen] = useState(false)
  const chat = useTopicChat()
  const triggerPipeline = useTriggerPipeline()
  const updateAction = useUpdateTopicAction()
  const { data: session } = useTopicReviewSession(selectedTopicId)
  const { setActivePipelineRunId } = useDashboardStore()

  const activeCandidates = candidateView === 'today' ? candidates ?? [] : poolCandidates ?? []
  const activeIsLoading = candidateView === 'today' ? isLoading : isPoolLoading

  useEffect(() => {
    if (activeCandidates.length === 0) {
      setSelectedTopicId(null)
      return
    }
    if (!selectedTopicId || !activeCandidates.some((topic) => topic.id === selectedTopicId)) {
      setSelectedTopicId(activeCandidates[0].id)
    }
  }, [activeCandidates, selectedTopicId])

  const selectedTopic = useMemo(() => {
    return session?.topic ?? activeCandidates.find((topic) => topic.id === selectedTopicId) ?? null
  }, [activeCandidates, selectedTopicId, session])

  const messages = session?.messages ?? []
  const displayMessages = [...messages, ...optimisticMessages]
  const signals = session?.signals ?? []

  const sendMessage = async (message: string) => {
    const trimmed = message.trim()
    if (!selectedTopic || !trimmed || chat.isPending) return
    const history: ChatMessage[] = messages.map((msg) => ({
      role: msg.role,
      content: msg.content,
    }))
    setChatError(null)
    setInputValue('')
    setOptimisticMessages((current) => [...current, { role: 'user', content: trimmed }])
    try {
      await chat.mutateAsync({ topicId: selectedTopic.id, message: trimmed, history })
      setOptimisticMessages([])
    } catch {
      setOptimisticMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: '这次回复没有成功返回。我已经保留了你的问题，可以稍后重试。',
        },
      ])
      setChatError('回复失败，请检查后端或模型配置后重试。')
    }
  }

  const decide = (action: 'approved' | 'skipped') => {
    if (!selectedTopic) return
    updateAction.mutate({
      topicId: selectedTopic.id,
      action,
      notes: decisionNote || undefined,
    })
    setDecisionNote('')
  }

  const runPipeline = () => {
    triggerPipeline.mutate(
      {
        languages: [''],
        limit: 5,
        source: 'legacy',
        model: 'qwen3.6-max-preview',
      },
      {
        onSuccess: (data) => {
          setActivePipelineRunId(data.run_id)
        },
      }
    )
  }

  const workspaceGridClass = contextOpen
    ? 'xl:grid-cols-[280px_minmax(440px,1fr)_320px]'
    : 'xl:grid-cols-[300px_minmax(520px,1fr)]'

  return (
    <div className="xl:h-[calc(100vh-2.5rem)] min-h-[680px] flex flex-col gap-3">
      <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900">今日选题工作台</h2>
          <p className="text-sm text-gray-500 mt-1">
            Agent 每天筛出 5-8 个候选，通过对话审稿并沉淀长期偏好。
          </p>
        </div>
        <div className="text-xs text-gray-500 border border-gray-200 rounded-md px-3 py-2 bg-white">
          自动抓取 09:00 · GitHub Trending · 已筛出 {candidates?.length ?? 0} 个候选
        </div>
      </div>

      <div className={`grid grid-cols-1 ${workspaceGridClass} gap-3 flex-1 min-h-0`}>
        <CandidateList
          candidates={activeCandidates}
          view={candidateView}
          poolStatus={poolStatus}
          selectedTopicId={selectedTopicId}
          isLoading={activeIsLoading}
          isPipelineRunning={triggerPipeline.isPending}
          onViewChange={setCandidateView}
          onPoolStatusChange={setPoolStatus}
          onSelect={setSelectedTopicId}
          onShowPool={() => {
            setCandidateView('pool')
            setPoolStatus(undefined)
          }}
          onRunPipeline={runPipeline}
        />

        <ChatWorkspace
          topic={selectedTopic}
          messages={displayMessages}
          error={chatError}
          contextOpen={contextOpen}
          inputValue={inputValue}
          isSending={chat.isPending}
          onInputChange={setInputValue}
          onSend={sendMessage}
          onToggleContext={() => setContextOpen((open) => !open)}
        />

        {contextOpen && (
          <ContextPanel
            topic={selectedTopic}
            signals={signals}
            decisionNote={decisionNote}
            onDecisionNoteChange={setDecisionNote}
            onApprove={() => decide('approved')}
            onSkip={() => decide('skipped')}
            onClose={() => setContextOpen(false)}
            isDeciding={updateAction.isPending}
          />
        )}
      </div>
    </div>
  )
}

function CandidateList({
  candidates,
  view,
  poolStatus,
  selectedTopicId,
  isLoading,
  isPipelineRunning,
  onViewChange,
  onPoolStatusChange,
  onSelect,
  onShowPool,
  onRunPipeline,
}: {
  candidates: Topic[]
  view: 'today' | 'pool'
  poolStatus?: string
  selectedTopicId: number | null
  isLoading: boolean
  isPipelineRunning: boolean
  onViewChange: (view: 'today' | 'pool') => void
  onPoolStatusChange: (status: string | undefined) => void
  onSelect: (id: number) => void
  onShowPool: () => void
  onRunPipeline: () => void
}) {
  return (
    <aside className="bg-white border border-gray-200 rounded-lg min-h-[360px] xl:min-h-0 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">
            {view === 'today' ? '今日候选' : '候选池'}
          </h3>
          <span className="text-xs text-gray-500">{candidates.length}</span>
        </div>
        <div className="grid grid-cols-2 gap-1 rounded-md bg-gray-100 p-1">
          <button
            onClick={() => onViewChange('today')}
            className={`rounded px-2 py-1.5 text-xs font-medium ${
              view === 'today' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
            }`}
          >
            今日
          </button>
          <button
            onClick={() => onViewChange('pool')}
            className={`rounded px-2 py-1.5 text-xs font-medium ${
              view === 'pool' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
            }`}
          >
            候选池
          </button>
        </div>
        {view === 'pool' && (
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => onPoolStatusChange(undefined)}
              className={`rounded-full px-2 py-1 text-[11px] ${
                !poolStatus ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-500'
              }`}
            >
              全部
            </button>
            {poolFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => onPoolStatusChange(filter.value)}
                className={`rounded-full px-2 py-1 text-[11px] ${
                  poolStatus === filter.value
                    ? 'bg-gray-900 text-white'
                    : 'bg-gray-100 text-gray-500'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="p-3 space-y-2 overflow-y-auto">
        {isLoading && <div className="text-sm text-gray-400 py-8 text-center">加载中...</div>}
        {candidates.map((topic) => (
          <button
            key={topic.id}
            onClick={() => onSelect(topic.id)}
            className={`w-full text-left border rounded-md p-3 transition-colors ${
              selectedTopicId === topic.id
                ? 'border-blue-300 bg-blue-50'
                : 'border-gray-200 bg-white hover:bg-gray-50'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium text-sm text-gray-900 truncate">
                {topic.project_name || '未知项目'}
              </div>
              <span className="text-xs font-semibold text-gray-700">
                {(topic.final_score ?? 0).toFixed(1)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">
              {topic.why_post || topic.differentiation_angle || '暂无推荐理由'}
            </p>
            <div className="mt-2 flex items-center justify-between">
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  stateStyles[topic.review_state] ?? stateStyles.未聊
                }`}
              >
                {topic.review_state}
              </span>
              <span className="text-xs text-gray-400">{topic.engagement_estimate}</span>
            </div>
            {view === 'pool' && (
              <div className="mt-2 flex items-center justify-between text-[11px] text-gray-400">
                <span>出现 {topic.seen_count ?? 1} 次</span>
                <span>{formatShortDate(topic.last_seen_at || topic.created_at)}</span>
              </div>
            )}
          </button>
        ))}
        {!isLoading && candidates.length === 0 && (
          <div className="py-8 text-center">
            <div className="text-sm text-gray-400">
              {view === 'today' ? '暂无今日候选' : '候选池暂无匹配结果'}
            </div>
            {view === 'today' && (
              <div className="mt-4 grid grid-cols-1 gap-2">
                <button
                  onClick={onShowPool}
                  className="w-full rounded-md border border-gray-200 px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
                >
                  查看候选池
                </button>
                <button
                  onClick={onRunPipeline}
                  disabled={isPipelineRunning}
                  className="w-full rounded-md bg-gray-900 px-3 py-2 text-xs text-white hover:bg-gray-800 disabled:opacity-40"
                >
                  {isPipelineRunning ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Loader2 size={12} className="animate-spin" />
                      正在运行
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5">
                      <Play size={12} />
                      重新运行 Pipeline
                    </span>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="mt-auto border-t border-gray-100 p-3">
        <button
          onClick={onShowPool}
          className="w-full text-xs text-gray-500 border border-gray-200 rounded-md py-2 hover:bg-gray-50"
        >
          {view === 'today' ? '查看候选池' : '回到候选池全部'}
        </button>
      </div>
    </aside>
  )
}

function ChatWorkspace({
  topic,
  messages,
  error,
  contextOpen,
  inputValue,
  isSending,
  onInputChange,
  onSend,
  onToggleContext,
}: {
  topic: Topic | null
  messages: ChatMessage[]
  error: string | null
  contextOpen: boolean
  inputValue: string
  isSending: boolean
  onInputChange: (value: string) => void
  onSend: (message: string) => void
  onToggleContext: () => void
}) {
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null)
  const hasMessages = messages.length > 0
  const hasAssistantMessages = messages.some((message) => message.role === 'assistant')
  const quickPrompts = [
    '为什么这个项目值得做成视频？',
    '换成 60 秒短视频角度',
    '普通观众能看懂吗？',
    '给我一个开头钩子',
  ]

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, isSending, error])

  return (
    <section className="bg-white border border-gray-200 rounded-lg min-h-[560px] xl:min-h-0 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-9 w-9 shrink-0 rounded-full bg-gray-900 text-white flex items-center justify-center">
            <Bot size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <h3 className="font-semibold text-gray-900 truncate">选题审稿 Agent</h3>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-green-50 text-green-700">
                在线
              </span>
            </div>
            <p className="text-xs text-gray-500 truncate">
              {topic?.project_name
                ? `正在讨论 ${topic.project_name}`
                : '从左侧选择一个候选后开始对话'}
            </p>
          </div>
          <button
            onClick={onToggleContext}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
              contextOpen
                ? 'border-gray-300 bg-gray-100 text-gray-800'
                : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            {contextOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
            上下文
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-gray-50/70 px-4 py-5 space-y-5">
        {!topic && (
          <ChatBubble role="assistant">
            先从左侧选择一个今日候选。我会基于项目证据、视频化潜力和你的历史偏好，陪你把这个选题聊清楚。
          </ChatBubble>
        )}

        {topic && !hasAssistantMessages && (
          <>
            <ChatBubble role="assistant">
              我先给出初步判断：这个项目适合从「{topic.differentiation_angle || '实战演示'}」
              切入。我们可以继续聊它的爆点、风险、受众，或者把它改写成更适合短视频的脚本。
            </ChatBubble>
          </>
        )}

        {topic && !hasMessages && (
          <div className="ml-11 flex flex-wrap gap-2">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => onSend(prompt)}
                disabled={isSending}
                className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 disabled:opacity-40"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {messages.map((message, index) => (
          <ChatBubble key={`${message.role}-${index}`} role={message.role}>
            {message.content}
          </ChatBubble>
        ))}

        {hasMessages && topic && (
          <div className="ml-11 flex flex-wrap gap-2">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => onSend(prompt)}
                disabled={isSending}
                className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 disabled:opacity-40"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {isSending && (
          <ChatBubble role="assistant">
            <span className="inline-flex items-center gap-2 text-gray-500">
              <Loader2 size={14} className="animate-spin" />
              <span>正在整理判断</span>
              <span className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-typing-dot" />
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-typing-dot [animation-delay:120ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-typing-dot [animation-delay:240ms]" />
              </span>
            </span>
          </ChatBubble>
        )}

        {error && (
          <div className="ml-11 text-xs text-red-600 bg-red-50 border border-red-100 rounded-full px-3 py-1.5 w-fit">
            {error}
          </div>
        )}

        <div ref={scrollAnchorRef} />
      </div>

      <div className="border-t border-gray-200 bg-white p-3">
        <div className="rounded-2xl border border-gray-300 bg-white p-2 shadow-sm focus-within:ring-2 focus-within:ring-gray-900/10 focus-within:border-gray-500">
          <textarea
            value={inputValue}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                onSend(inputValue)
              }
            }}
            disabled={!topic || isSending}
            placeholder="像聊天一样问 Agent：这个选题适不适合我的账号？"
            rows={2}
            className="w-full resize-none px-2 py-1 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none disabled:bg-white disabled:text-gray-400"
          />
          <div className="flex items-center justify-between gap-3 pt-1">
            <span className="text-[11px] text-gray-400">
              Enter 发送，Shift+Enter 换行；你的偏好会沉淀为评分信号
            </span>
            <button
              onClick={() => onSend(inputValue)}
              disabled={!topic || !inputValue.trim() || isSending}
              className="h-8 w-8 shrink-0 rounded-full bg-gray-900 text-white flex items-center justify-center transition-all duration-150 hover:scale-105 active:scale-95 disabled:opacity-40 disabled:hover:scale-100"
              aria-label="发送消息"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

function ChatBubble({
  role,
  children,
}: {
  role: 'user' | 'assistant'
  children: React.ReactNode
}) {
  const isUser = role === 'user'

  return (
    <div
      className={`flex items-end gap-2 animate-chat-bubble-in ${
        isUser ? 'justify-end' : 'justify-start'
      }`}
    >
      {!isUser && (
        <div className="h-9 w-9 shrink-0 rounded-full bg-gray-900 text-white flex items-center justify-center">
          <Bot size={17} />
        </div>
      )}
      <div
        className={`max-w-[min(78%,720px)] rounded-2xl px-4 py-3 text-sm leading-6 whitespace-pre-wrap shadow-sm ${
          isUser
            ? 'rounded-br-md bg-gray-900 text-white'
            : 'rounded-bl-md bg-white border border-gray-200 text-gray-800'
        }`}
      >
        {children}
      </div>
      {isUser && (
        <div className="h-9 w-9 shrink-0 rounded-full bg-gray-200 text-gray-700 flex items-center justify-center">
          <UserRound size={17} />
        </div>
      )}
    </div>
  )
}

function ContextPanel({
  topic,
  signals,
  decisionNote,
  onDecisionNoteChange,
  onApprove,
  onSkip,
  onClose,
  isDeciding,
}: {
  topic: Topic | null
  signals: ReviewSignal[]
  decisionNote: string
  onDecisionNoteChange: (value: string) => void
  onApprove: () => void
  onSkip: () => void
  onClose: () => void
  isDeciding: boolean
}) {
  return (
    <aside className="bg-white border border-gray-200 rounded-lg min-h-[520px] xl:min-h-0 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-gray-500">选题上下文</div>
          <h3 className="font-semibold text-gray-900 truncate">{topic?.project_name || '未选择'}</h3>
        </div>
        <button
          onClick={onClose}
          className="h-7 w-7 shrink-0 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-700 flex items-center justify-center"
          aria-label="关闭上下文"
          title="关闭上下文"
        >
          <PanelRightClose size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        <PanelBlock title="项目证据">
          <InfoRow label="GitHub" value={topic?.github_url || '暂无'} />
          <InfoRow label="推荐理由" value={topic?.why_post || '暂无'} />
          <InfoRow label="目标受众" value={topic?.target_audience || '暂无'} />
        </PanelBlock>

        <PanelBlock title="初始评分拆解">
          <ScoreBar label="综合评分" value={topic?.final_score ?? 0} />
          <ScoreBar label="互动潜力" value={engagementToScore(topic?.engagement_estimate)} />
          <ScoreBar label="视频化确定性" value={signals.length > 0 ? 7 : 5} />
        </PanelBlock>

        <PanelBlock title="对话信号">
          <div className="flex flex-wrap gap-2">
            {signals.map((signal, index) => (
              <span key={`${signal.label}-${index}`} className="text-xs px-2 py-1 rounded border border-gray-200 bg-gray-50 text-gray-600">
                {signalTypeLabel[signal.signal_type] || '信号'} · {signal.label}
              </span>
            ))}
            {signals.length === 0 && <span className="text-sm text-gray-400">还没有记录到偏好信号</span>}
          </div>
        </PanelBlock>

        <PanelBlock title="内容草稿">
          <div className="flex gap-1 bg-gray-100 p-1 rounded-md w-fit mb-2">
            <span className="px-2 py-1 bg-white rounded text-xs">推文</span>
            <span className="px-2 py-1 text-xs text-gray-500">60秒脚本</span>
            <span className="px-2 py-1 text-xs text-gray-500">大纲</span>
          </div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap border border-gray-200 rounded-md p-3 bg-gray-50 min-h-24">
            {topic?.user_edited_draft_tweet || topic?.draft_tweet || '暂无草稿'}
          </div>
        </PanelBlock>
      </div>

      <div className="border-t border-gray-200 p-4 space-y-3">
        <textarea
          value={decisionNote}
          onChange={(event) => onDecisionNoteChange(event.target.value)}
          placeholder="记录采纳或跳过的理由，这会进入长期学习信号。"
          className="w-full min-h-20 px-3 py-2 text-sm border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-gray-900"
        />
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={onApprove}
            disabled={!topic || isDeciding}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-gray-900 text-white text-sm disabled:opacity-40"
          >
            <CheckCircle size={14} />
            采纳
          </button>
          <button
            onClick={onSkip}
            disabled={!topic || isDeciding}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-md border border-gray-300 text-gray-700 text-sm disabled:opacity-40"
          >
            <XCircle size={14} />
            跳过
          </button>
          <button className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-md border border-gray-300 text-gray-600 text-sm">
            <Clock size={14} />
            暂存
          </button>
        </div>
      </div>
    </aside>
  )
}

function PanelBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 mb-2">{title}</h4>
      {children}
    </div>
  )
}

function formatShortDate(value: string | null) {
  if (!value) return '暂无时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无时间'
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-2 text-sm py-1.5 border-b border-gray-100 last:border-0">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-700 break-words">{value}</span>
    </div>
  )
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const percent = Math.max(0, Math.min(100, value * 10))
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="text-gray-500">{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-gray-500 rounded-full" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

function engagementToScore(value?: string): number {
  if (value === 'high') return 9
  if (value === 'medium') return 6
  if (value === 'low') return 3
  return 5
}
