export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isError?: boolean
}

export interface Settings {
  provider: string
  model: string
  sessionId: string
  systemPrompt: string
  deepResearch: boolean
}

export interface ProviderInfo {
  name: string
  available: boolean
  models: string[]
}

export interface ApiStatus {
  status: string
  providers: ProviderInfo[]
  tavily_available: boolean
}

export interface ModelInfo {
  id: string
  name: string
  description?: string
  context_length?: number
  pricing?: {
    prompt?: string
    completion?: string
  }
}

export interface ModelsResponse {
  provider: string
  models: ModelInfo[]
  error?: string
}

export interface ProgressEvent {
  step: string
  status: string | 'pending' | 'in_progress' | 'completed' | 'failed'
  detail: string
  progress: number
  tool?: string
  arguments?: Record<string, unknown> | undefined
}
