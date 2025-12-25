import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check, X, RefreshCw, FileText, RotateCcw, ChevronDown, ChevronUp, Search, MessageSquare, Globe } from 'lucide-react'
import { Settings, ApiStatus, ModelInfo } from '../lib/types'
import SearchableSelect, { SelectOption } from '../components/SearchableSelect'

// Common timezones for the dropdown
const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Moscow',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Hong_Kong',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Pacific/Auckland',
]

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

interface SettingsPageProps {
  settings: Settings
  onSettingsChange: (settings: Settings) => void
  apiStatus: ApiStatus | null
  onSaveSettings: () => void
  isSaving: boolean
  saveStatus: 'idle' | 'saving' | 'saved' | 'error'
}

export default function SettingsPage({
  settings,
  onSettingsChange,
  apiStatus,
  onSaveSettings,
  isSaving,
  saveStatus,
}: SettingsPageProps) {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [showPromptEditor, setShowPromptEditor] = useState(false)

  useEffect(() => {
    if (settings.provider) {
      fetchModels(settings.provider)
    }
  }, [settings.provider])

  const fetchModels = async (provider: string) => {
    setIsLoadingModels(true)
    setModelsError(null)
    
    try {
      const response = await fetch('/api/models/' + provider)
      const data = await response.json()
      
      if (data.error) {
        setModelsError(data.error)
        setModels([])
      } else {
        setModels(data.models || [])
        if (!settings.model && data.models?.length > 0) {
          onSettingsChange({
            ...settings,
            model: data.models[0].id,
          })
        }
      }
    } catch (error) {
      setModelsError('Failed to fetch models')
      setModels([])
    } finally {
      setIsLoadingModels(false)
    }
  }

  const resetSystemPrompt = () => {
    onSettingsChange({
      ...settings,
      systemPrompt: DEFAULT_SYSTEM_PROMPT,
    })
  }

  const availableProviders = apiStatus?.providers.filter(p => p.available) || []

  const modelOptions: SelectOption[] = models.map(model => ({
    id: model.id,
    name: model.name,
    description: model.description,
    contextLength: model.context_length,
    pricing: model.pricing,
  }))

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link 
                to="/" 
                className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="hidden sm:inline">Back to Chat</span>
              </Link>
              <div className="h-6 w-px bg-gray-700 hidden sm:block" />
              <h1 className="text-lg sm:text-xl font-semibold">Settings</h1>
            </div>
            <Link
              to="/"
              className="flex items-center gap-2 px-3 py-2 sm:px-4 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors text-sm sm:text-base"
            >
              <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5" />
              <span className="hidden sm:inline">Open Chat</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <div className="space-y-6 sm:space-y-8">
          
          {/* Status Section */}
          <section className="bg-gray-800 rounded-xl p-4 sm:p-6">
            <h2 className="text-lg font-semibold mb-4">System Status</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <StatusCard
                label="API Server"
                status={apiStatus?.status === 'ok'}
              />
              <StatusCard
                label="Tavily Search"
                status={apiStatus?.tavily_available || false}
              />
              <StatusCard
                label="Models Loaded"
                status={models.length > 0}
                detail={models.length > 0 ? models.length + ' available' : undefined}
              />
            </div>
          </section>

          {/* Provider & Model Section */}
          <section className="bg-gray-800 rounded-xl p-4 sm:p-6">
            <h2 className="text-lg font-semibold mb-4">LLM Configuration</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Provider */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Provider
                </label>
                <select
                  value={settings.provider}
                  onChange={(e) => {
                    onSettingsChange({
                      ...settings,
                      provider: e.target.value,
                      model: '',
                    })
                  }}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
                >
                  {availableProviders.map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Model */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-400">
                    Model
                  </label>
                  <button
                    onClick={() => fetchModels(settings.provider)}
                    disabled={isLoadingModels}
                    className="p-1.5 hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                    title="Refresh models"
                  >
                    <RefreshCw className={'w-4 h-4 text-gray-400 ' + (isLoadingModels ? 'animate-spin' : '')} />
                  </button>
                </div>
                <SearchableSelect
                  options={modelOptions}
                  value={settings.model}
                  onChange={(model) => onSettingsChange({ ...settings, model })}
                  placeholder="Search and select a model..."
                  isLoading={isLoadingModels}
                  error={modelsError || undefined}
                />
                {settings.model && (
                  <p className="mt-2 text-xs text-gray-500">
                    Selected: {settings.model}
                  </p>
                )}
              </div>
            </div>

            {/* Available Providers */}
            <div className="mt-6 pt-6 border-t border-gray-700">
              <h3 className="text-sm font-medium text-gray-400 mb-3">Available Providers</h3>
              <div className="flex flex-wrap gap-2">
                {apiStatus?.providers.map((provider) => (
                  <span
                    key={provider.name}
                    className={'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm ' + 
                      (provider.available 
                        ? 'bg-green-600/20 text-green-400' 
                        : 'bg-gray-700 text-gray-500'
                      )}
                  >
                    {provider.available ? (
                      <Check className="w-3.5 h-3.5" />
                    ) : (
                      <X className="w-3.5 h-3.5" />
                    )}
                    {provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* Research Mode Section */}
          <section className="bg-gray-800 rounded-xl p-4 sm:p-6">
            <h2 className="text-lg font-semibold mb-4">Research Mode</h2>
            <button
              onClick={() => onSettingsChange({ ...settings, deepResearch: !settings.deepResearch })}
              className={'w-full flex items-center justify-between px-4 sm:px-6 py-4 rounded-xl border-2 transition-all ' +
                (settings.deepResearch
                  ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                  : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                )}
            >
              <div className="flex items-center gap-3 sm:gap-4">
                <div className={'p-2 sm:p-3 rounded-xl ' + (settings.deepResearch ? 'bg-purple-600/30' : 'bg-gray-600')}>
                  <Search className={'w-5 h-5 sm:w-6 sm:h-6 ' + (settings.deepResearch ? 'text-purple-400' : 'text-gray-400')} />
                </div>
                <div className="text-left">
                  <div className="font-semibold text-base sm:text-lg">Deep Research</div>
                  <div className="text-xs sm:text-sm opacity-75">
                    {settings.deepResearch 
                      ? 'Multi-step research with page scraping enabled' 
                      : 'Quick web search only - faster responses'}
                  </div>
                </div>
              </div>
              <div className={'w-14 h-7 sm:w-16 sm:h-8 rounded-full p-1 transition-all flex-shrink-0 ' +
                (settings.deepResearch ? 'bg-purple-500' : 'bg-gray-600')}>
                <div className={'w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white transition-all ' +
                  (settings.deepResearch ? 'translate-x-7 sm:translate-x-8' : 'translate-x-0')} />
              </div>
            </button>
          </section>

          {/* Timezone Section */}
          <section className="bg-gray-800 rounded-xl p-4 sm:p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Globe className="w-5 h-5" />
              Timezone
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Set your timezone for accurate date/time in search queries (e.g., "news from yesterday")
            </p>
            <select
              value={settings.timezone}
              onChange={(e) => onSettingsChange({ ...settings, timezone: e.target.value })}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz.replace(/_/g, ' ')} ({getTimezoneOffset(tz)})
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-2">
              Current time in selected timezone: {getCurrentTimeInTimezone(settings.timezone)}
            </p>
          </section>

          {/* System Prompt Section */}
          <section className="bg-gray-800 rounded-xl p-4 sm:p-6">
            <button
              onClick={() => setShowPromptEditor(!showPromptEditor)}
              className="w-full flex items-center justify-between text-lg font-semibold hover:text-gray-300 transition-colors"
            >
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                <span>System Prompt</span>
              </div>
              {showPromptEditor ? (
                <ChevronUp className="w-5 h-5" />
              ) : (
                <ChevronDown className="w-5 h-5" />
              )}
            </button>
            
            {showPromptEditor && (
              <div className="mt-4 space-y-3">
                <textarea
                  value={settings.systemPrompt}
                  onChange={(e) => onSettingsChange({ ...settings, systemPrompt: e.target.value })}
                  className="w-full h-64 sm:h-80 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                  placeholder="Enter system prompt..."
                />
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <span className="text-xs text-gray-500">
                    {settings.systemPrompt.length} characters
                  </span>
                  <button
                    onClick={resetSystemPrompt}
                    className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-300 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Reset to default
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Save Button */}
          <div className="sticky bottom-4 sm:bottom-6">
            <button
              onClick={onSaveSettings}
              disabled={isSaving}
              className={'w-full flex items-center justify-center gap-2 px-6 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg ' +
                (saveStatus === 'saved' 
                  ? 'bg-green-600 hover:bg-green-700' 
                  : saveStatus === 'error'
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed'
                )}
            >
              {isSaving ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : saveStatus === 'saved' ? (
                <>
                  <Check className="w-5 h-5" />
                  Settings Saved!
                </>
              ) : saveStatus === 'error' ? (
                <>
                  <X className="w-5 h-5" />
                  Failed to Save
                </>
              ) : (
                <>
                  <Check className="w-5 h-5" />
                  Save Settings
                </>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

function StatusCard({ label, status, detail }: { label: string; status: boolean; detail?: string }) {
  return (
    <div className={'p-4 rounded-lg border ' + 
      (status ? 'bg-green-600/10 border-green-600/30' : 'bg-gray-700 border-gray-600')}>
      <div className="flex items-center justify-between">
        <span className="font-medium">{label}</span>
        {status ? (
          <Check className="w-5 h-5 text-green-400" />
        ) : (
          <X className="w-5 h-5 text-red-400" />
        )}
      </div>
      <p className={'text-sm mt-1 ' + (status ? 'text-green-400' : 'text-gray-500')}>
        {status ? (detail || 'Ready') : 'Not configured'}
      </p>
    </div>
  )
}

function getTimezoneOffset(timezone: string): string {
  try {
    const now = new Date()
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      timeZoneName: 'shortOffset',
    })
    const parts = formatter.formatToParts(now)
    const offsetPart = parts.find(p => p.type === 'timeZoneName')
    return offsetPart?.value || ''
  } catch {
    return ''
  }
}

function getCurrentTimeInTimezone(timezone: string): string {
  try {
    return new Date().toLocaleString('en-US', {
      timeZone: timezone,
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return 'Invalid timezone'
  }
}
