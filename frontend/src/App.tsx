import { useState, useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import { Settings, ApiStatus } from './lib/types'
import { ChatProvider } from './contexts/ChatContext'
import { ThemeProvider } from './contexts/ThemeContext'

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
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null)
  const [settings, setSettings] = useState<Settings>({
    provider: 'openai',
    model: '',
    sessionId: 'default',
    systemPrompt: DEFAULT_SYSTEM_PROMPT,
    deepResearch: false,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC',
  })
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
          timezone: settingsData?.timezone ?? (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'),
          maxTokens: settingsData?.max_tokens,
          multiAgentMode: settingsData?.multi_agent_mode ?? false,
          // Per-agent model configuration
          masterAgentModel: settingsData?.master_agent_model,
          masterAgentProvider: settingsData?.master_agent_provider,
          plannerAgentModel: settingsData?.planner_agent_model,
          plannerAgentProvider: settingsData?.planner_agent_provider,
          searchScraperAgentModel: settingsData?.search_scraper_agent_model,
          searchScraperAgentProvider: settingsData?.search_scraper_agent_provider,
          toolExecutorAgentModel: settingsData?.tool_executor_agent_model,
          toolExecutorAgentProvider: settingsData?.tool_executor_agent_provider,
          // Per-agent system prompts
          masterAgentSystemPrompt: settingsData?.master_agent_system_prompt,
          plannerAgentSystemPrompt: settingsData?.planner_agent_system_prompt,
          searchScraperAgentSystemPrompt: settingsData?.search_scraper_agent_system_prompt,
        }

        console.log('Final settings after initialization:', newSettings)
        setSettings(newSettings)
        setIsInitialized(true)
      } catch (error) {
        console.error('Failed to initialize app:', error)
        setIsInitialized(true)
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
          timezone: settings.timezone,
          max_tokens: settings.maxTokens,
          multi_agent_mode: settings.multiAgentMode,
          // Per-agent model configuration
          master_agent_model: settings.masterAgentModel,
          master_agent_provider: settings.masterAgentProvider,
          planner_agent_model: settings.plannerAgentModel,
          planner_agent_provider: settings.plannerAgentProvider,
          search_scraper_agent_model: settings.searchScraperAgentModel,
          search_scraper_agent_provider: settings.searchScraperAgentProvider,
          tool_executor_agent_model: settings.toolExecutorAgentModel,
          tool_executor_agent_provider: settings.toolExecutorAgentProvider,
          // Per-agent system prompts
          master_agent_system_prompt: settings.masterAgentSystemPrompt,
          planner_agent_system_prompt: settings.plannerAgentSystemPrompt,
          search_scraper_agent_system_prompt: settings.searchScraperAgentSystemPrompt,
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

  if (!isInitialized) {
    return (
      <ThemeProvider>
        <div className="flex h-screen items-center justify-center bg-white dark:bg-gray-900">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-gray-500 dark:text-gray-400">Loading...</p>
          </div>
        </div>
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
      <BrowserRouter>
        <ChatProvider>
        <Routes>
        <Route 
          path="/" 
          element={
            <ChatPage 
              settings={settings}
              apiStatus={apiStatus}
            />
          } 
        />
        <Route 
          path="/settings" 
          element={
            <SettingsPage 
              settings={settings}
              onSettingsChange={setSettings}
              apiStatus={apiStatus}
              onSaveSettings={saveSettings}
              isSaving={isSaving}
              saveStatus={saveStatus}
            />
          } 
        />
        </Routes>
        </ChatProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
