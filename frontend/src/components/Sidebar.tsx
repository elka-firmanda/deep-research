import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Trash2, Settings as SettingsIcon, Check, X, RefreshCw, FileText, RotateCcw, ChevronDown, ChevronUp, Search } from 'lucide-react'
import { Settings, ApiStatus, ModelInfo } from '../lib/types'
import SearchableSelect, { SelectOption } from './SearchableSelect'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  settings: Settings
  onSettingsChange: (settings: Settings) => void
  apiStatus: ApiStatus | null
  onClearChat: () => void
  onResetPrompt: () => void
  onSaveSettings: () => void
  isSaving: boolean
  saveStatus: 'idle' | 'saving' | 'saved' | 'error'
}

export default function Sidebar({
  isOpen,
  onToggle,
  settings,
  onSettingsChange,
  apiStatus,
  onClearChat,
  onResetPrompt,
  onSaveSettings,
  isSaving,
  saveStatus,
}: SidebarProps) {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [showPromptEditor, setShowPromptEditor] = useState(false)

  // Fetch models when provider changes
  useEffect(() => {
    if (settings.provider) {
      fetchModels(settings.provider)
    }
  }, [settings.provider])

  const fetchModels = async (provider: string) => {
    setIsLoadingModels(true)
    setModelsError(null)
    
    try {
      const response = await fetch(`/api/models/${provider}`)
      const data = await response.json()
      
      if (data.error) {
        setModelsError(data.error)
        setModels([])
      } else {
        setModels(data.models || [])
        // Auto-select first model if none selected
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

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed left-0 top-1/2 -translate-y-1/2 bg-gray-800 p-2 rounded-r-lg hover:bg-gray-700 transition-colors z-10"
      >
        <ChevronRight className="w-5 h-5" />
      </button>
    )
  }

  const availableProviders = apiStatus?.providers.filter(p => p.available) || []

  // Convert models to SelectOption format
  const modelOptions: SelectOption[] = models.map(model => ({
    id: model.id,
    name: model.name,
    description: model.description,
    contextLength: model.context_length,
    pricing: model.pricing,
  }))

  return (
    <aside className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <SettingsIcon className="w-5 h-5" />
          <span className="font-semibold">Settings</span>
        </div>
        <button
          onClick={onToggle}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-6 overflow-y-auto">
        {/* Status */}
        <section>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Status</h3>
          <div className="space-y-2">
            <StatusItem
              label="API"
              status={apiStatus?.status === 'ok'}
            />
            <StatusItem
              label="Tavily Search"
              status={apiStatus?.tavily_available || false}
            />
          </div>
        </section>

        {/* Provider Selection */}
        <section>
          <h3 className="text-sm font-medium text-gray-400 mb-2">LLM Provider</h3>
          <select
            value={settings.provider}
            onChange={(e) => {
              const newProvider = e.target.value
              onSettingsChange({
                ...settings,
                provider: newProvider,
                model: '', // Reset model when provider changes
              })
            }}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {availableProviders.map((provider) => (
              <option key={provider.name} value={provider.name}>
                {provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}
              </option>
            ))}
          </select>
        </section>

        {/* Model Selection - Searchable */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-400">Model</h3>
            <button
              onClick={() => fetchModels(settings.provider)}
              disabled={isLoadingModels}
              className="p-1 hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
              title="Refresh models"
            >
              <RefreshCw className={`w-4 h-4 text-gray-400 ${isLoadingModels ? 'animate-spin' : ''}`} />
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
            <div className="mt-2 text-xs text-gray-500">
              Selected: {settings.model}
            </div>
          )}
        </section>

        {/* Deep Research Toggle */}
        <section>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Research Mode</h3>
          <button
            onClick={() => onSettingsChange({ ...settings, deepResearch: !settings.deepResearch })}
            className={`w-full flex items-center justify-between px-4 py-3 rounded-lg border transition-all ${
              settings.deepResearch
                ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${settings.deepResearch ? 'bg-purple-600/30' : 'bg-gray-600'}`}>
                <Search className={`w-5 h-5 ${settings.deepResearch ? 'text-purple-400' : 'text-gray-400'}`} />
              </div>
              <div className="text-left">
                <div className="font-medium">Deep Research</div>
                <div className="text-xs opacity-75">
                  {settings.deepResearch ? 'Multi-step research with page scraping' : 'Quick web search only'}
                </div>
              </div>
            </div>
            <div className={`w-12 h-6 rounded-full p-1 transition-all ${
              settings.deepResearch ? 'bg-purple-500' : 'bg-gray-600'
            }`}>
              <div className={`w-4 h-4 rounded-full bg-white transition-all ${
                settings.deepResearch ? 'translate-x-6' : 'translate-x-0'
              }`} />
            </div>
          </button>
        </section>

        {/* System Prompt Editor */}
        <section>
          <button
            onClick={() => setShowPromptEditor(!showPromptEditor)}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-400 mb-2 hover:text-gray-300 transition-colors"
          >
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              <span>System Prompt</span>
            </div>
            {showPromptEditor ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
          
          {showPromptEditor && (
            <div className="space-y-2">
              <textarea
                value={settings.systemPrompt}
                onChange={(e) => onSettingsChange({ ...settings, systemPrompt: e.target.value })}
                className="w-full h-64 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Enter system prompt..."
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  {settings.systemPrompt.length} characters
                </span>
                <button
                  onClick={onResetPrompt}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300 transition-colors"
                  title="Reset to default prompt"
                >
                  <RotateCcw className="w-3 h-3" />
                  Reset to default
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Available Providers */}
        <section>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Available Providers</h3>
          <div className="space-y-2">
            {apiStatus?.providers.map((provider) => (
              <StatusItem
                key={provider.name}
                label={provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}
                status={provider.available}
              />
            ))}
          </div>
        </section>

        {/* Model Count */}
        {models.length > 0 && (
          <section>
            <div className="text-xs text-gray-500">
              {models.length} models available from {settings.provider}
            </div>
          </section>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700 space-y-2">
        <button
          onClick={onSaveSettings}
          disabled={isSaving}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >
          {isSaving ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : saveStatus === 'saved' ? (
            <>
              <Check className="w-4 h-4" />
              Saved!
            </>
          ) : saveStatus === 'error' ? (
            <>
              <X className="w-4 h-4" />
              Failed
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              Save Settings
            </>
          )}
        </button>
        <button
          onClick={onClearChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Clear Chat
        </button>
      </div>
    </aside>
  )
}

function StatusItem({ label, status }: { label: string; status: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      {status ? (
        <span className="flex items-center gap-1 text-green-400">
          <Check className="w-4 h-4" />
          Ready
        </span>
      ) : (
        <span className="flex items-center gap-1 text-red-400">
          <X className="w-4 h-4" />
          Not configured
        </span>
      )}
    </div>
  )
}
