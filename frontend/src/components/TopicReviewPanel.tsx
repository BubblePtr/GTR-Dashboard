import { useState, useEffect, useRef } from 'react'
import { X, Send, Sparkles, MessageCircle, Lightbulb, RotateCcw, CheckCircle, XCircle, Save } from 'lucide-react'
import type { Topic, ChatMessage } from '../types'
import { useTopicChat, useUpdateTopicContent, useUpdateTopicAction } from '../hooks/useApi'

type DraftTab = 'tweet' | 'script' | 'outline'

const draftTabLabels: Record<DraftTab, string> = {
  tweet: '推文',
  script: '脚本',
  outline: '大纲',
}

const draftFieldMap: Record<DraftTab, 'draft_tweet' | 'draft_script' | 'draft_outline'> = {
  tweet: 'draft_tweet',
  script: 'draft_script',
  outline: 'draft_outline',
}

const draftEditedFieldMap: Record<DraftTab, 'user_edited_draft_tweet' | 'user_edited_draft_script' | 'user_edited_draft_outline'> = {
  tweet: 'user_edited_draft_tweet',
  script: 'user_edited_draft_script',
  outline: 'user_edited_draft_outline',
}

const quickActions = [
  { key: 'refine_tweet', label: '润色推文', icon: Sparkles, preset: '请帮我润色这条推文，让它更吸引人，同时保持简洁。' },
  { key: 'refine_script', label: '生成脚本', icon: MessageCircle, preset: '请根据这个项目生成一个 60 秒左右的视频口播脚本。' },
  { key: 'explain', label: '解释选题', icon: Lightbulb, preset: '请详细解释为什么这个项目值得选题，它的核心亮点是什么？' },
  { key: 'new_angle', label: '换个角度', icon: RotateCcw, preset: '请提供一个和当前差异化角度不同的切入方式。' },
]

interface TopicReviewPanelProps {
  topic: Topic | null
  isOpen: boolean
  onClose: () => void
}

export default function TopicReviewPanel({ topic, isOpen, onClose }: TopicReviewPanelProps) {
  const [activeTab, setActiveTab] = useState<DraftTab>('tweet')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [pendingRefinedContent, setPendingRefinedContent] = useState<{ action: string; content: string } | null>(null)
  const [drafts, setDrafts] = useState({ tweet: '', script: '', outline: '' })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const chatMutation = useTopicChat()
  const updateContent = useUpdateTopicContent()
  const updateAction = useUpdateTopicAction()

  // Initialize local drafts from topic when it changes
  useEffect(() => {
    if (topic) {
      setMessages([])
      setInputValue('')
      setPendingRefinedContent(null)
      setActiveTab('tweet')
      setDrafts({
        tweet: topic.user_edited_draft_tweet ?? topic.draft_tweet ?? '',
        script: topic.user_edited_draft_script ?? topic.draft_script ?? '',
        outline: topic.user_edited_draft_outline ?? topic.draft_outline ?? '',
      })
    }
  }, [topic?.id])

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!isOpen || !topic) return null

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isChatLoading) return

    const userMsg: ChatMessage = { role: 'user', content: message }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInputValue('')
    setIsChatLoading(true)

    try {
      const result = await chatMutation.mutateAsync({
        topicId: topic.id,
        message,
        history: messages,
      })

      const assistantMsg: ChatMessage = { role: 'assistant', content: result.response }
      setMessages((prev) => [...prev, assistantMsg])

      if (result.refined_content && result.action) {
        setPendingRefinedContent({ action: result.action, content: result.refined_content })
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '抱歉，请求失败了，请重试。' },
      ])
    } finally {
      setIsChatLoading(false)
    }
  }

  const handleQuickAction = (preset: string) => {
    handleSendMessage(preset)
  }

  const handleApplyRefinedContent = () => {
    if (!pendingRefinedContent) return

    const action = pendingRefinedContent.action
    let targetTab: DraftTab | null = null

    if (action === 'refine_tweet') targetTab = 'tweet'
    else if (action === 'refine_script') targetTab = 'script'
    else if (action === 'refine_outline') targetTab = 'outline'

    if (targetTab) {
      setActiveTab(targetTab)
      setDrafts((prev) => ({ ...prev, [targetTab!]: pendingRefinedContent.content }))
      updateContent.mutate({
        topicId: topic.id,
        content: { [draftEditedFieldMap[targetTab]]: pendingRefinedContent.content },
      })
    }

    setPendingRefinedContent(null)
  }

  const getDraftValue = (tab: DraftTab): string => {
    return drafts[tab]
  }

  const getOriginalDraftValue = (tab: DraftTab): string => {
    return topic[draftFieldMap[tab]] ?? ''
  }

  const handleDraftChange = (tab: DraftTab, value: string) => {
    setDrafts((prev) => ({ ...prev, [tab]: value }))
    updateContent.mutate({
      topicId: topic.id,
      content: { [draftEditedFieldMap[tab]]: value },
    })
  }

  const handleDecision = (action: 'approved' | 'skipped') => {
    updateContent.mutate(
      {
        topicId: topic.id,
        content: {
          user_edited_draft_tweet: drafts.tweet,
          user_edited_draft_script: drafts.script,
          user_edited_draft_outline: drafts.outline,
        },
      },
      {
        onSuccess: () => {
          updateAction.mutate({ topicId: topic.id, action })
          onClose()
        },
      }
    )
  }

  const handleSaveAndClose = () => {
    updateContent.mutate(
      {
        topicId: topic.id,
        content: {
          user_edited_draft_tweet: drafts.tweet,
          user_edited_draft_script: drafts.script,
          user_edited_draft_outline: drafts.outline,
        },
      },
      {
        onSuccess: () => {
          onClose()
        },
      }
    )
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-[640px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-gray-900 truncate">
                {topic.project_name || '未知项目'}
              </h3>
              {topic.final_score !== null && topic.final_score !== undefined && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium border border-orange-100">
                  评分: {topic.final_score.toFixed(1)}
                </span>
              )}
            </div>
            {topic.github_url && (
              <a
                href={topic.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline truncate block"
              >
                {topic.github_url}
              </a>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-md hover:bg-gray-200 transition-colors flex-shrink-0"
          >
            <X size={18} className="text-gray-500" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {/* Topic info section */}
          <div className="px-6 py-4 space-y-3 border-b border-gray-100">
            {topic.why_post && (
              <div>
                <span className="text-xs font-medium text-gray-500">选题理由</span>
                <p className="text-sm text-gray-700 mt-0.5">{topic.why_post}</p>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {topic.differentiation_angle && (
                <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded text-xs">差异化: {topic.differentiation_angle}</span>
              )}
              {topic.target_audience && (
                <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">受众: {topic.target_audience}</span>
              )}
              <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                互动: {topic.engagement_estimate}
              </span>
            </div>
          </div>

          {/* Draft tabs */}
          <div className="px-6 py-4 border-b border-gray-100">
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit mb-3">
              {(Object.keys(draftTabLabels) as DraftTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    activeTab === tab
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {draftTabLabels[tab]}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              {/* Original draft (read-only) */}
              {getOriginalDraftValue(activeTab) && (
                <div>
                  <span className="text-xs font-medium text-gray-400">原始草稿</span>
                  <div className="mt-1 p-3 bg-gray-50 rounded-md text-sm text-gray-500 whitespace-pre-wrap">
                    {getOriginalDraftValue(activeTab)}
                  </div>
                </div>
              )}

              {/* Editable draft */}
              <div>
                <span className="text-xs font-medium text-gray-500">编辑中</span>
                <textarea
                  value={getDraftValue(activeTab)}
                  onChange={(e) => handleDraftChange(activeTab, e.target.value)}
                  className="mt-1 w-full p-3 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[120px] resize-y"
                  placeholder={`在此编辑${draftTabLabels[activeTab]}...`}
                />
              </div>
            </div>
          </div>

          {/* Chat section */}
          <div className="px-6 py-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">与 Agent 对话</h4>

            {/* Messages */}
            <div className="space-y-3 mb-4 max-h-[300px] overflow-y-auto">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] px-3 py-2 rounded-lg text-sm ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                    {msg.role === 'assistant' && pendingRefinedContent && idx === messages.length - 1 && (
                      <button
                        onClick={handleApplyRefinedContent}
                        className="mt-2 text-xs px-2 py-1 rounded bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                      >
                        查看润色结果
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {isChatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 px-3 py-2 rounded-lg text-sm text-gray-500">
                    Agent 思考中...
                  </div>
                </div>
              )}
              {pendingRefinedContent && !isChatLoading && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                  <div className="text-xs font-medium text-yellow-800 mb-1">
                    Agent 提供了新的{draftTabLabels[activeTab]}版本：
                  </div>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap mb-2">
                    {pendingRefinedContent.content}
                  </div>
                  <button
                    onClick={handleApplyRefinedContent}
                    className="text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700"
                  >
                    应用此版本
                  </button>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick actions */}
            <div className="flex flex-wrap gap-2 mb-3">
              {quickActions.map((qa) => (
                <button
                  key={qa.key}
                  onClick={() => handleQuickAction(qa.preset)}
                  disabled={isChatLoading}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                >
                  <qa.icon size={12} />
                  {qa.label}
                </button>
              ))}
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage(inputValue)
                  }
                }}
                placeholder="输入消息与 Agent 对话..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isChatLoading}
              />
              <button
                onClick={() => handleSendMessage(inputValue)}
                disabled={isChatLoading || !inputValue.trim()}
                className="px-3 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between gap-3">
          <button
            onClick={handleSaveAndClose}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
          >
            <Save size={14} />
            暂存
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => handleDecision('skipped')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium border border-gray-300 bg-white text-gray-600 hover:bg-gray-50"
            >
              <XCircle size={14} />
              跳过
            </button>
            <button
              onClick={() => handleDecision('approved')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium border border-green-200 bg-green-50 text-green-700 hover:bg-green-100"
            >
              <CheckCircle size={14} />
              采纳
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
