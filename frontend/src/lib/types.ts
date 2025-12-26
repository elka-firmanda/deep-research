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
  timezone: string
  maxTokens?: number  // Max tokens for response generation
  multiAgentMode?: boolean  // Enable multi-agent orchestration (experimental)
  // Per-agent model configuration (for multi-agent mode)
  masterAgentModel?: string  // Model for MasterAgent synthesis
  masterAgentProvider?: string  // Provider for MasterAgent
  plannerAgentModel?: string  // Model for PlannerAgent
  plannerAgentProvider?: string  // Provider for PlannerAgent
  searchScraperAgentModel?: string  // Model for SearchScraperAgent
  searchScraperAgentProvider?: string  // Provider for SearchScraperAgent
  toolExecutorAgentModel?: string  // Model for ToolExecutorAgent (usually not needed)
  toolExecutorAgentProvider?: string  // Provider for ToolExecutorAgent
  // Per-agent system prompts (for multi-agent mode)
  masterAgentSystemPrompt?: string  // System prompt for MasterAgent
  plannerAgentSystemPrompt?: string  // System prompt for PlannerAgent
  searchScraperAgentSystemPrompt?: string  // System prompt for SearchScraperAgent
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
  serpapi_available: boolean
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
  source?: string  // Source subagent: 'planner_agent', 'search_scraper_agent', 'tool_executor_agent', 'master_agent'
}

export interface Conversation {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  metadata?: Record<string, unknown>
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
}

export interface ConversationMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  metadata?: Record<string, unknown>
}
