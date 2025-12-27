import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Send, Settings, Loader2, Search, Globe, FileText, Sparkles, Trash2, Copy, Check } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Settings as SettingsType, Message, ProgressEvent, ApiStatus, ConversationMessage } from '../lib/types'
import Sidebar from '../components/Sidebar'
import { useChat } from '../contexts/ChatContext'
import { streamManager } from '../lib/streamManager'

interface ChatPageProps {
  settings: SettingsType
  apiStatus: ApiStatus | null
}

export default function ChatPage({ settings, apiStatus }: ChatPageProps) {
  const { conversationId, setConversationId, messages, setMessages, isLoading, setIsLoading, currentProgress, setCurrentProgress, addMessage } = useChat()
  const [input, setInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isInitialized, setIsInitialized] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const location = useLocation()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentProgress])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  // Mark as initialized after mount
  useEffect(() => {
    setIsInitialized(true)
  }, [])

  // Refresh conversation when coming back to the page or after refresh
  useEffect(() => {
    if (!isInitialized || !conversationId || location.pathname !== '/') return

    let pollInterval: ReturnType<typeof setInterval> | null = null
    let initialTimeout: ReturnType<typeof setTimeout> | null = null
    let pollCount = 0
    const MAX_POLL_COUNT = 15 // Stop polling after 30 seconds (15 polls * 2 seconds)

    const refreshConversation = async () => {
      // Don't refresh if we're actively sending a new message or loading a response
      // This prevents overwriting the new message with stale data from DB
      // and prevents resetting progress state during streaming
      if (isSending || isLoading) {
        pollCount = 0 // Reset poll count when actively sending/loading
        return
      }

      try {
        const response = await fetch(`/api/conversations/${conversationId}/messages`)
        if (response.ok) {
          const data = await response.json()
          const loadedMessages: Message[] = data.messages.map((m: ConversationMessage) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at),
          }))

          setMessages(loadedMessages)

          // Check if conversation is complete (even number of messages)
          // If odd, last user message doesn't have a response yet
          const isComplete = loadedMessages.length % 2 === 0
          const isIncomplete = loadedMessages.length % 2 !== 0 && loadedMessages.length > 0

          if (isComplete && loadedMessages.length > 0) {
            setIsLoading(false)
            setCurrentProgress(null)
            pollCount = 0

            // Stop polling if conversation is complete
            if (pollInterval) {
              clearInterval(pollInterval)
              pollInterval = null
            }
          } else if (isIncomplete) {
            pollCount++

            // If we've polled too many times, the stream was likely interrupted
            // Stop polling and clear loading state to allow user to continue
            if (pollCount >= MAX_POLL_COUNT) {
              console.warn('Polling timeout: stream may have been interrupted')
              setIsLoading(false)
              setCurrentProgress(null)
              if (pollInterval) {
                clearInterval(pollInterval)
                pollInterval = null
              }
              return
            }

            // If incomplete, ensure we're in loading state and polling
            setIsLoading(true)

            // Ensure polling is active
            if (!pollInterval) {
              pollInterval = setInterval(refreshConversation, 2000)
            }
          }
        }
      } catch (error) {
        console.error('Failed to refresh conversation:', error)
      }
    }

    // Delay initial refresh to ensure ChatContext is fully initialized
    initialTimeout = setTimeout(() => {
      refreshConversation()
      // Polling will be started/stopped inside refreshConversation based on conversation state
    }, 100)

    return () => {
      if (initialTimeout) clearTimeout(initialTimeout)
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [isInitialized, location.pathname, conversationId, isSending, isLoading])

  const sendMessage = async (content: string) => {
    setIsSending(true)
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    
    addMessage(userMessage)
    setIsLoading(true)
    setCurrentProgress(null)
    setInput('')

    const abortController = new AbortController()
    const streamId = streamManager.generateId()
    let streamRegistered = false
    let finalResponse = ''
    let streamingContent = ''
    let streamingMessageId = ''
    let buffer = ''
    let messageAdded = false

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          session_id: settings.sessionId,
          conversation_id: conversationId || undefined,
          provider: settings.provider,
          model: settings.model || undefined,
          stream: true,
          system_prompt: settings.systemPrompt || undefined,
          deep_research: settings.deepResearch,
          timezone: settings.timezone,
          max_tokens: settings.maxTokens || undefined,
          multi_agent_mode: settings.multiAgentMode || false,
          // Per-agent models and providers (only sent if multi_agent_mode is enabled)
          master_agent_model: settings.masterAgentModel || undefined,
          master_agent_provider: settings.masterAgentProvider || undefined,
          planner_agent_model: settings.plannerAgentModel || undefined,
          planner_agent_provider: settings.plannerAgentProvider || undefined,
          search_scraper_agent_model: settings.searchScraperAgentModel || undefined,
          search_scraper_agent_provider: settings.searchScraperAgentProvider || undefined,
          tool_executor_agent_model: settings.toolExecutorAgentModel || undefined,
          tool_executor_agent_provider: settings.toolExecutorAgentProvider || undefined,
          // Per-agent system prompts (only sent if multi_agent_mode is enabled)
          master_agent_system_prompt: settings.masterAgentSystemPrompt || undefined,
          planner_agent_system_prompt: settings.plannerAgentSystemPrompt || undefined,
          search_scraper_agent_system_prompt: settings.searchScraperAgentSystemPrompt || undefined,
        }),
        signal: abortController.signal,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Request failed')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      
      if (!reader) {
        throw new Error('No response body')
      }

      // Register stream with manager to keep it alive even if component unmounts
      streamManager.startStream(streamId, abortController, reader, conversationId)
      streamRegistered = true

      const processEvent = (event: { type: string; content?: string; step?: string; status?: string; detail?: string; progress?: number; tool?: string; arguments?: unknown; conversation_id?: string; agent_name?: string; agent_icon?: string }) => {
        switch (event.type) {
          case 'progress':
            setCurrentProgress({
              step: event.step || '',
              status: event.status || '',
              detail: event.detail || '',
              progress: event.progress || 0,
              agent_name: event.agent_name,
              agent_icon: event.agent_icon,
            })
            break

          case 'tool_call':
            setCurrentProgress({
              step: 'tool_call',
              status: 'in_progress',
              detail: event.detail || ('Using ' + event.tool + '...'),
              progress: 0,
              tool: event.tool,
              arguments: (event.arguments as Record<string, unknown> | undefined) || {},
              agent_name: event.agent_name,
              agent_icon: event.agent_icon,
            })
            break

          case 'thinking':
            setCurrentProgress({
              step: 'thinking',
              status: 'in_progress',
              detail: event.content || '',
              progress: 0,
              agent_name: event.agent_name,
              agent_icon: event.agent_icon,
            })
            break

          case 'response_chunk':
            // Accumulate streaming content
            streamingContent += event.content || ''
            // Create or update streaming message
            if (!streamingMessageId) {
              streamingMessageId = (Date.now() + 1).toString()
              const streamingMessage: Message = {
                id: streamingMessageId,
                role: 'assistant',
                content: streamingContent,
                timestamp: new Date(),
              }
              setMessages(prev => [...prev, streamingMessage])
              messageAdded = true
              // Clear progress when streaming starts
              setCurrentProgress(null)
            } else {
              // Update existing streaming message
              setMessages(prev =>
                prev.map(msg =>
                  msg.id === streamingMessageId
                    ? { ...msg, content: streamingContent }
                    : msg
                )
              )
            }
            break

          case 'response':
            // Final complete response - update the streaming message if it exists
            finalResponse = event.content || ''
            if (streamingMessageId) {
              setMessages(prev =>
                prev.map(msg =>
                  msg.id === streamingMessageId
                    ? { ...msg, content: finalResponse }
                    : msg
                )
              )
            }
            break
          
          case 'conversation_id':
            if (event.conversation_id) {
              setConversationId(event.conversation_id)
            }
            break
          
          case 'done':
            // Only add new message if we didn't stream chunks
            if (finalResponse && !messageAdded) {
              const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: finalResponse,
                timestamp: new Date(),
              }
              setMessages(prev => [...prev, assistantMessage])
              messageAdded = true
            }
            setCurrentProgress(null)
            break
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const eventChunks = buffer.split('\n\n')
        buffer = eventChunks.pop() || ''

        for (const eventChunk of eventChunks) {
          const lines = eventChunk.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') continue
              try {
                const event = JSON.parse(data)
                processEvent(event)
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        }
      }

      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try {
              const event = JSON.parse(data)
              processEvent(event)
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }

      // Backup: add message if we got a response but didn't add it via streaming or done event
      if (finalResponse && !messageAdded) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: finalResponse,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, assistantMessage])
      }
      setCurrentProgress(null)
    } catch (error) {
      // Only show error if it's not an abort (which happens when navigating away)
      if (!abortController.signal.aborted) {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Error: ' + (error instanceof Error ? error.message : 'Failed to connect to the server.'),
          timestamp: new Date(),
          isError: true,
        }
        setMessages(prev => [...prev, errorMessage])
        setCurrentProgress(null)
      }
    } finally {
      // Clean up stream manager
      if (streamRegistered) {
        streamManager.removeStream(streamId)
      }
      setIsLoading(false)
      setIsSending(false)
    }
  }

  const clearChat = async () => {
    try {
      await fetch('/api/session/' + settings.sessionId + '/reset', {
        method: 'POST',
      })
      setMessages([])
      setConversationId(null)
    } catch (error) {
      console.error('Failed to reset session:', error)
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setConversationId(null)
    setCurrentProgress(null)
    setIsLoading(false)
    setSidebarOpen(false)
    // Clear all chat-related localStorage items
    localStorage.removeItem('chat_messages')
    localStorage.removeItem('chat_conversation_id')
    localStorage.removeItem('chat_is_loading')
    localStorage.removeItem('chat_progress')
    // Clear all active streams
    streamManager.clearAll()
  }

  const handleSelectConversation = async (id: string) => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/conversations/${id}/messages`)
      if (response.ok) {
        const data = await response.json()
        const loadedMessages: Message[] = data.messages.map((m: ConversationMessage) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
        }))
        setMessages(loadedMessages)
        setConversationId(id)
        setSidebarOpen(false)
      }
    } catch (error) {
      console.error('Failed to load conversation:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteConversation = (id: string) => {
    // If the deleted conversation is the current one, clear the chat
    if (id === conversationId) {
      setMessages([])
      setConversationId(null)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      sendMessage(input.trim())
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        currentConversationId={conversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${sidebarOpen ? 'lg:ml-72' : ''}`}>
        {/* Header */}
        <header className="flex items-center justify-between px-3 sm:px-6 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Spacer for sidebar toggle button when closed */}
            {!sidebarOpen && <div className="w-10" />}
            <div className="p-1.5 sm:p-2 bg-blue-600 rounded-lg">
              <Sparkles className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-semibold">AI Research Agent</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400 hidden sm:block">
                {settings.provider} / {settings.model || 'default'}
                {settings.deepResearch && ' • Deep Research'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="p-2 text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="Clear chat"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            )}
            <Link
              to="/settings"
              className="flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <Settings className="w-5 h-5" />
              <span className="hidden sm:inline text-sm">Settings</span>
            </Link>
          </div>
        </header>

      {/* Status bar (mobile) */}
      <div className="sm:hidden px-3 py-2 bg-gray-100/50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2 overflow-x-auto">
        <span className="flex items-center gap-1 flex-shrink-0">
          <span className={'w-2 h-2 rounded-full ' + (apiStatus?.status === 'ok' ? 'bg-green-500' : 'bg-red-500')} />
          {settings.provider}
        </span>
        <span className="text-gray-400 dark:text-gray-600">|</span>
        <span className="truncate">{settings.model || 'default model'}</span>
        {settings.deepResearch && (
          <>
            <span className="text-gray-400 dark:text-gray-600">|</span>
            <span className="text-purple-500 dark:text-purple-400 flex-shrink-0">Deep Research</span>
          </>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full px-4 py-8">
            <div className="text-center max-w-2xl mx-auto">
              <div className="text-5xl sm:text-6xl mb-4">🔍</div>
              <h2 className="text-xl sm:text-2xl font-bold mb-2">AI Research Agent</h2>
              <p className="text-gray-500 dark:text-gray-400 text-sm sm:text-base mb-6 px-4">
                Your intelligent research assistant. Ask questions, explore topics,
                and get comprehensive answers with real sources.
              </p>
              
              {/* Example prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 px-2">
                <ExamplePrompt
                  icon={<Search className="w-4 h-4" />}
                  text="Latest AI developments"
                  onClick={() => sendMessage("What are the latest developments in artificial intelligence this year?")}
                />
                <ExamplePrompt
                  icon={<Globe className="w-4 h-4" />}
                  text="Climate solutions research"
                  onClick={() => sendMessage("Research the most promising climate change solutions being developed right now")}
                />
                <ExamplePrompt
                  icon={<FileText className="w-4 h-4" />}
                  text="Compare React vs Vue"
                  onClick={() => sendMessage("Compare React and Vue.js - which should I choose for a new web project?")}
                />
                <ExamplePrompt
                  icon={<Sparkles className="w-4 h-4" />}
                  text="Explain quantum computing"
                  onClick={() => sendMessage("Explain quantum computing in simple terms with real-world applications")}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto px-3 sm:px-6 py-4 space-y-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            
            {/* Progress Indicator */}
            {isLoading && currentProgress && (
              <ProgressCard progress={currentProgress} />
            )}
            
            {isLoading && !currentProgress && (
              <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 px-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Starting...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 p-3 sm:p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2 sm:gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything... research topics, compare options, explain concepts"
                className="w-full bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-3 pr-12 resize-none overflow-hidden focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm sm:text-base min-h-[48px] max-h-[200px]"
                rows={1}
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 bottom-2 p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors text-white"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center hidden sm:block">
            Press Enter to send • Shift + Enter for new line
          </p>
        </form>
      </div>
      </div>
    </div>
  )
}

function ProgressCard({ progress }: { progress: ProgressEvent }) {
  return (
    <div className="flex items-center gap-3 px-2 py-2">
      <Loader2 className="w-5 h-5 animate-spin text-blue-500 dark:text-blue-400 flex-shrink-0" />
      <div className="flex items-center gap-2 text-sm">
        {progress.agent_icon && progress.agent_name && (
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {progress.agent_icon} {progress.agent_name}
          </span>
        )}
        {progress.agent_name && <span className="text-gray-400 dark:text-gray-500">|</span>}
        <span className="text-gray-600 dark:text-gray-300">{progress.detail}</span>
      </div>
    </div>
  )
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  const preRef = useRef<HTMLPreElement>(null)

  const handleCopy = () => {
    if (preRef.current) {
      const code = preRef.current.textContent || ''
      navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title={copied ? 'Copied!' : 'Copy code'}
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-500 dark:text-green-400" />
        ) : (
          <Copy className="w-4 h-4 text-gray-600 dark:text-gray-300" />
        )}
      </button>
      <pre ref={preRef} className="bg-gray-100 dark:bg-gray-900 rounded-lg overflow-x-auto my-3 sm:my-4 -mx-4 sm:mx-0">
        {children}
      </pre>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={'flex ' + (isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={'rounded-2xl px-4 py-3 ' +
          (isUser
            ? 'bg-blue-600 text-white max-w-[85%] sm:max-w-[75%]'
            : message.isError
            ? 'bg-red-100 dark:bg-red-900/50 border border-red-300 dark:border-red-700 max-w-full'
            : 'bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 max-w-full'
          )}
        style={{ fontFamily: 'Inter, sans-serif' }}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm sm:text-base">{message.content}</p>
        ) : (
          <div className="markdown-content text-sm sm:text-base">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                table: ({ children }) => (
                  <div className="overflow-x-auto my-4 -mx-4 px-4">
                    <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600 text-sm">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-200 dark:bg-gray-700">{children}</thead>
                ),
                tbody: ({ children }) => (
                  <tbody className="divide-y divide-gray-300 dark:divide-gray-600">{children}</tbody>
                ),
                tr: ({ children }) => (
                  <tr className="hover:bg-gray-200/50 dark:hover:bg-gray-700/50">{children}</tr>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2 text-left text-xs sm:text-sm font-semibold text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-xs sm:text-sm text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600">
                    {children}
                  </td>
                ),
                a: ({ href, children }) => {
                  const childText = String(children)
                  const isCitation = /^\[\d+\]$/.test(childText)

                  return (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={isCitation
                        ? "text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 no-underline font-medium"
                        : "text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 underline break-all"
                      }
                      title={href}
                    >
                      {children}
                    </a>
                  )
                },
                sup: ({ children }) => (
                  <sup className="text-xs text-blue-600 dark:text-blue-400 ml-0.5 cursor-pointer hover:text-blue-500 dark:hover:text-blue-300">
                    {children}
                  </sup>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className
                  return isInline ? (
                    <code className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs sm:text-sm text-pink-600 dark:text-pink-300 break-all" {...props}>
                      {children}
                    </code>
                  ) : (
                    <code className={(className || '') + ' block bg-gray-100 dark:bg-gray-900 p-3 sm:p-4 rounded-lg overflow-x-auto text-xs sm:text-sm'} {...props}>
                      {children}
                    </code>
                  )
                },
                pre: ({ children }) => (
                  <CodeBlock>{children}</CodeBlock>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-outside space-y-1 my-2 ml-5">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-outside space-y-1 my-2 ml-5">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-gray-600 dark:text-gray-300 pl-1">{children}</li>
                ),
                h1: ({ children }) => (
                  <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100 mt-6 mb-3">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-gray-100 mt-5 mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mt-4 mb-2">{children}</h3>
                ),
                p: ({ children }) => (
                  <p className="text-gray-600 dark:text-gray-300 my-2 leading-relaxed">{children}</p>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-gray-400 dark:border-gray-500 pl-3 sm:pl-4 my-4 text-gray-500 dark:text-gray-400 italic">
                    {children}
                  </blockquote>
                ),
                hr: () => (
                  <hr className="border-gray-300 dark:border-gray-600 my-4 sm:my-6" />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

function ExamplePrompt({ icon, text, onClick }: { icon: React.ReactNode; text: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 text-left px-4 py-3 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl transition-colors group"
    >
      <div className="p-2 bg-gray-200 dark:bg-gray-700 group-hover:bg-gray-300 dark:group-hover:bg-gray-600 rounded-lg text-gray-500 dark:text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors">
        {icon}
      </div>
      <span className="text-sm text-gray-600 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">{text}</span>
    </button>
  )
}
