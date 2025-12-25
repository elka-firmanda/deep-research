import { useState, useRef, useEffect } from 'react'
import { Send, Menu, Loader2, Search, Globe, FileText, CheckCircle2, Circle, ArrowRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Message, ProgressEvent } from '../lib/types'

interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
  currentProgress: ProgressEvent | null
  onSendMessage: (message: string) => void
  onToggleSidebar: () => void
}

export default function ChatWindow({
  messages,
  isLoading,
  currentProgress,
  onSendMessage,
  onToggleSidebar,
}: ChatWindowProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentProgress])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim())
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <header className="flex items-center gap-4 px-4 py-3 border-b border-gray-700">
        <button
          onClick={onToggleSidebar}
          className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-semibold">AI Search Agent</h1>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-xl font-semibold mb-2">AI Search Agent</h2>
            <p className="text-center max-w-md">
              Ask me anything! I can search the web, perform deep research on complex topics,
              and provide comprehensive answers with sources.
            </p>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
              <ExamplePrompt
                text="What are the latest developments in AI?"
                onClick={() => onSendMessage("What are the latest developments in AI?")}
              />
              <ExamplePrompt
                text="Deep research: Climate change solutions"
                onClick={() => onSendMessage("Do a deep research on the most promising climate change solutions being developed right now")}
              />
              <ExamplePrompt
                text="Compare React vs Vue in 2024"
                onClick={() => onSendMessage("Compare React and Vue.js in 2024 - which should I choose for a new project?")}
              />
              <ExamplePrompt
                text="Explain quantum computing simply"
                onClick={() => onSendMessage("Explain quantum computing in simple terms with real-world examples")}
              />
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}
        
        {/* Progress Indicator */}
        {isLoading && currentProgress && (
          <ProgressCard progress={currentProgress} />
        )}
        
        {isLoading && !currentProgress && (
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Starting...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-700">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything... (Press Enter to send, Shift+Enter for new line)"
            className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={1}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  )
}

function ProgressCard({ progress }: { progress: ProgressEvent }) {
  const getStepIcon = (step: string) => {
    switch (step) {
      case 'generate_queries':
        return <FileText className="w-4 h-4" />
      case 'search':
        return <Search className="w-4 h-4" />
      case 'scrape_pages':
        return <Globe className="w-4 h-4" />
      case 'synthesize':
        return <FileText className="w-4 h-4" />
      case 'tool_call':
        if (progress.tool === 'deep_search') return <Search className="w-4 h-4" />
        if (progress.tool === 'web_scraper') return <Globe className="w-4 h-4" />
        return <Search className="w-4 h-4" />
      default:
        return <Loader2 className="w-4 h-4 animate-spin" />
    }
  }

  const getStepName = (step: string) => {
    switch (step) {
      case 'start':
        return 'Starting Research'
      case 'generate_queries':
        return 'Generating Research Questions'
      case 'search':
        return 'Searching the Web'
      case 'scrape_pages':
        return 'Reading Page Content'
      case 'synthesize':
        return 'Analyzing & Synthesizing'
      case 'tool_call':
        if (progress.tool === 'deep_search') return 'Deep Research'
        if (progress.tool === 'tavily_search') return 'Web Search'
        if (progress.tool === 'web_scraper') return 'Reading Webpage'
        return progress.tool || 'Processing'
      case 'thinking':
        return 'Thinking'
      default:
        return step
    }
  }

  const steps = [
    { id: 'generate_queries', label: 'Research Questions' },
    { id: 'search', label: 'Web Search' },
    { id: 'scrape_pages', label: 'Read Pages' },
    { id: 'synthesize', label: 'Synthesize' },
  ]

  const currentStepIndex = steps.findIndex(s => s.id === progress.step)

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-blue-600/20 rounded-lg">
          {getStepIcon(progress.step)}
        </div>
        <div className="flex-1">
          <div className="font-medium text-gray-200">{getStepName(progress.step)}</div>
          <div className="text-sm text-gray-400">{progress.detail}</div>
        </div>
        {progress.status === 'in_progress' && (
          <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
        )}
      </div>

      {/* Progress Bar */}
      {progress.progress > 0 && (
        <div className="mb-4">
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 transition-all duration-500 ease-out"
              style={{ width: `${progress.progress}%` }}
            />
          </div>
          <div className="text-xs text-gray-500 mt-1 text-right">{progress.progress}%</div>
        </div>
      )}

      {/* Step indicators for deep search */}
      {(progress.tool === 'deep_search' || ['generate_queries', 'search', 'scrape_pages', 'synthesize'].includes(progress.step)) && (
        <div className="flex items-center justify-between text-xs">
          {steps.map((step, index) => {
            const isCompleted = index < currentStepIndex || (index === currentStepIndex && progress.status === 'completed')
            const isCurrent = index === currentStepIndex && progress.status === 'in_progress'
            const isPending = index > currentStepIndex

            return (
              <div key={step.id} className="flex items-center">
                <div className={`flex items-center gap-1.5 ${
                  isCompleted ? 'text-green-400' : isCurrent ? 'text-blue-400' : 'text-gray-500'
                }`}>
                  {isCompleted ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : isCurrent ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Circle className="w-4 h-4" />
                  )}
                  <span className={isPending ? 'text-gray-500' : ''}>{step.label}</span>
                </div>
                {index < steps.length - 1 && (
                  <ArrowRight className={`w-4 h-4 mx-2 ${
                    index < currentStepIndex ? 'text-green-400' : 'text-gray-600'
                  }`} />
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Tool arguments (optional, for debugging) */}
      {progress.arguments && Object.keys(progress.arguments).length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <div className="text-xs text-gray-500">
            {progress.tool === 'deep_search' && typeof progress.arguments === 'object' && 'query' in progress.arguments && (
              <span>Query: "{String((progress.arguments as Record<string, unknown>).query).slice(0, 100)}"</span>
            )}
            {progress.tool === 'web_scraper' && typeof progress.arguments === 'object' && 'url' in progress.arguments && (
              <span>URL: {String((progress.arguments as Record<string, unknown>).url).slice(0, 60)}...</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-3xl rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : message.isError
            ? 'bg-red-900/50 border border-red-700'
            : 'bg-gray-800 border border-gray-700'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="markdown-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                table: ({ children }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full border-collapse border border-gray-600">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-700">{children}</thead>
                ),
                tbody: ({ children }) => (
                  <tbody className="divide-y divide-gray-600">{children}</tbody>
                ),
                tr: ({ children }) => (
                  <tr className="hover:bg-gray-700/50">{children}</tr>
                ),
                th: ({ children }) => (
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-200 border border-gray-600">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-4 py-2 text-sm text-gray-300 border border-gray-600">
                    {children}
                  </td>
                ),
                a: ({ href, children }) => {
                  // Check if this is a citation link (inside sup or looks like [N])
                  const childText = String(children)
                  const isCitation = /^\[\d+\]$/.test(childText)
                  
                  return (
                    <a 
                      href={href} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className={isCitation 
                        ? "text-blue-400 hover:text-blue-300 no-underline font-medium"
                        : "text-blue-400 hover:text-blue-300 underline"
                      }
                      title={href}
                    >
                      {children}
                    </a>
                  )
                },
                sup: ({ children }) => (
                  <sup className="text-xs text-blue-400 ml-0.5 cursor-pointer hover:text-blue-300">
                    {children}
                  </sup>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className
                  return isInline ? (
                    <code className="bg-gray-700 px-1.5 py-0.5 rounded text-sm text-pink-300" {...props}>
                      {children}
                    </code>
                  ) : (
                    <code className={`${className} block bg-gray-800 p-4 rounded-lg overflow-x-auto text-sm`} {...props}>
                      {children}
                    </code>
                  )
                },
                pre: ({ children }) => (
                  <pre className="bg-gray-800 rounded-lg overflow-x-auto my-4">
                    {children}
                  </pre>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-gray-300">{children}</li>
                ),
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold text-gray-100 mt-6 mb-3">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold text-gray-100 mt-5 mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-semibold text-gray-100 mt-4 mb-2">{children}</h3>
                ),
                p: ({ children }) => (
                  <p className="text-gray-300 my-2 leading-relaxed">{children}</p>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-gray-500 pl-4 my-4 text-gray-400 italic">
                    {children}
                  </blockquote>
                ),
                hr: () => (
                  <hr className="border-gray-600 my-6" />
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

function ExamplePrompt({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left px-4 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors"
    >
      {text}
    </button>
  )
}
