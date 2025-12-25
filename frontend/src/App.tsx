import { useState, useEffect, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import Sidebar from './components/Sidebar'
import { Settings, Message, ApiStatus, ProgressEvent } from './lib/types'

const DEFAULT_SYSTEM_PROMPT = `You are an expert research assistant that produces comprehensive, well-sourced research reports. Your responses should read like Wikipedia articles or academic research summaries.

## Available Tools
1. **tavily_search**: Quick web search for current information, news, and facts.
2. **deep_search**: Comprehensive research that searches multiple queries, reads full page content, and synthesizes information. Use this for complex topics.
3. **web_scraper**: Read the full content of a specific webpage URL.

## Response Guidelines

### Writing Style
- Write in a formal, encyclopedic tone similar to Wikipedia
- Use complete paragraphs with flowing prose, not bullet points
- Provide comprehensive coverage of topic with depth and nuance
- Include relevant context, background, and implications
- Maintain objectivity and present multiple perspectives when applicable

### Citations (CRITICAL)
- Every factual claim MUST have a citation
- Use superscript numbers for citations: <sup>[[1]](URL)</sup>
- Place citations immediately after relevant sentence or claim
- Number citations sequentially starting from 1
- At the end, include a "## References" section listing all sources

### Citation Format Example
"Artificial intelligence has seen rapid advancement in recent years, with large language models demonstrating unprecedented capabilities in natural language understanding.<sup>[[1]](https://example.com/article1)</sup> These developments have sparked both excitement and concern among researchers and policymakers.<sup>[[2]](https://example.com/article2)</sup>"

### Structure
- Start with an introductory paragraph summarizing the topic
- Use ## headers to organize major sections
- Provide detailed paragraphs under each section
- End with a "## References" section listing all cited sources

### Important Rules
- ALWAYS search for information before answering - never make up facts
- If search results are insufficient, acknowledge limitations
- Cross-reference multiple sources when possible
- Include dates and specific details when available
- Every paragraph should have at least one citation`

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentProgress, setCurrentProgress] = useState<ProgressEvent | null>(null)
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null)
  const [settings, setSettings] = useState<Settings>({
    provider: 'openai',
    model: '',
    sessionId: 'default',
    systemPrompt: DEFAULT_SYSTEM_PROMPT,
    deepResearch: false,
  })
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [isInitialized, setIsInitialized] = useState(false)
  const initStarted = useRef(false)

  useEffect(() => {
    if (initStarted.current) return
    initStarted.current = true

    const initializeApp = async () => {
      try {
        const statusResponse = await fetch('/api/status')
        const statusData = await statusResponse.json()
        setApiStatus(statusData)

        const settingsResponse = await fetch('/api/settings/default')
        const settingsData = settingsResponse.ok ? await settingsResponse.json() : null

        console.log('Initializing app with:', { statusData, settingsData })

        const newSettings: Settings = {
          sessionId: 'default',
          provider: settingsData?.provider ?? (statusData.providers.find((p: { available: boolean }) => p.available)?.name || 'openai'),
          model: settingsData?.model ?? '',
          systemPrompt: settingsData?.system_prompt ?? DEFAULT_SYSTEM_PROMPT,
          deepResearch: settingsData?.deep_research ?? false,
        }

        console.log('Final settings after initialization:', newSettings)
        setSettings(newSettings)
        setIsInitialized(true)
      } catch (error) {
        console.error('Failed to initialize app:', error)
        setIsInitialized(true) // Still mark as initialized so UI shows
      }
    }

    initializeApp()
  }, [])

  const saveSettings = async () => {
    setIsSaving(true)
    setSaveStatus('saving')
    
    try {
      const response = await fetch('/api/settings/' + settings.sessionId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: settings.provider,
          model: settings.model,
          system_prompt: settings.systemPrompt,
          deep_research: settings.deepResearch,
        }),
      })
      
      if (response.ok) {
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else {
        setSaveStatus('error')
      }
    } catch (error) {
      console.error('Failed to save settings:', error)
      setSaveStatus('error')
    } finally {
      setIsSaving(false)
    }
  }

  const sendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setCurrentProgress(null)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          session_id: settings.sessionId,
          provider: settings.provider,
          model: settings.model || undefined,
          stream: true,
          system_prompt: settings.systemPrompt || undefined,
          deep_research: settings.deepResearch,
        }),
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

      let finalResponse = ''
      let buffer = ''
      let messageAdded = false

      const processEvent = (event: { type: string; content?: string; step?: string; status?: string; detail?: string; progress?: number; tool?: string; arguments?: unknown }) => {
        console.log('SSE event received:', event.type, event)
        
        switch (event.type) {
          case 'progress':
            setCurrentProgress({
              step: event.step || '',
              status: event.status || '',
              detail: event.detail || '',
              progress: event.progress || 0,
            })
            break
          
          case 'tool_call':
            setCurrentProgress({
              step: 'tool_call',
              status: 'in_progress',
              detail: 'Using ' + event.tool + '...',
              progress: 0,
              tool: event.tool,
              arguments: (event.arguments as Record<string, unknown> | undefined) || {},
            })
            break
          
          case 'thinking':
            setCurrentProgress({
              step: 'thinking',
              status: 'in_progress',
              detail: event.content || '',
              progress: 0,
            })
            break
          
          case 'response':
            finalResponse = event.content || ''
            break
          
          case 'done':
            console.log('Done event received, finalResponse length:', finalResponse.length)
            if (finalResponse) {
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
              console.warn('Failed to parse final buffer:', e)
            }
          }
        }
      }

      if (finalResponse && !messageAdded) {
        console.log('Fallback: Adding response that was never committed, length:', finalResponse.length)
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: finalResponse,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, assistantMessage])
        setCurrentProgress(null)
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Error: ' + (error instanceof Error ? error.message : 'Failed to connect to the server.'),
        timestamp: new Date(),
        isError: true,
      }
      setMessages(prev => [...prev, errorMessage])
      setCurrentProgress(null)
    } finally {
      setIsLoading(false)
    }
  }

  const clearChat = async () => {
    try {
      await fetch('/api/session/' + settings.sessionId + '/reset', {
        method: 'POST',
      })
      setMessages([])
    } catch (error) {
      console.error('Failed to reset session:', error)
    }
  }

  const resetSystemPrompt = () => {
    setSettings(prev => ({
      ...prev,
      systemPrompt: DEFAULT_SYSTEM_PROMPT,
    }))
  }

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        settings={settings}
        onSettingsChange={setSettings}
        apiStatus={apiStatus}
        onClearChat={clearChat}
        onResetPrompt={resetSystemPrompt}
        onSaveSettings={saveSettings}
        isSaving={isSaving}
        saveStatus={saveStatus}
      />
      
      <main className="flex-1 flex flex-col">
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          currentProgress={currentProgress}
          onSendMessage={sendMessage}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
      </main>
    </div>
  )
}

export default App
