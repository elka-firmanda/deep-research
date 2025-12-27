# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Search Agent is a full-stack web application that provides AI-powered research with web search capabilities. It supports multiple LLM providers (OpenAI, Anthropic, OpenRouter) and can operate in single-agent or multi-agent orchestration mode.

## Development Commands

### Backend (from `/backend`)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (from `/frontend`)
```bash
npm install
npm run dev      # Development server on port 5173
npm run build    # Production build
```

### Docker (full stack)
```bash
docker-compose up --build      # Start all services
docker-compose down            # Stop services
```

## Architecture

### Multi-Agent System

The application supports two modes controlled by the `use_multi_agent` setting:

**Single-Agent Mode**: `SearchAgent` handles all operations using function calling with available tools.

**Multi-Agent Mode**: `MasterAgent` orchestrates specialized subagents:
- **QueryAnalyzer** (`agents/query_analyzer.py`) - Classifies queries and determines execution strategy
- **PlannerAgent** (`agents/planner_agent.py`) - Breaks complex queries into research steps
- **SearchScraperAgent** (`agents/search_scraper_agent.py`) - Executes searches and synthesizes results
- **ToolExecutorAgent** (`agents/tool_executor_agent.py`) - Handles utility operations (datetime, etc.)

Query types: `simple_fact`, `simple_search`, `complex_research`, `time_based`, `comparison`, `general`
Execution strategies: `sequential`, `parallel`, `conditional`, `direct`

### Tools System

All tools extend `BaseTool` (`tools/base.py`) with async execution and OpenAI-compatible function calling schema:
- **TavilySearchTool** - AI-optimized web search
- **SerpApiSearchTool** - Google search via SerpAPI
- **DeepSearchTool** - Multi-query research with Wikipedia-style synthesis
- **WebScraperTool** - URL content extraction
- **DateTimeTool** - Timezone-aware temporal queries

### Backend Structure

```
backend/app/
├── main.py              # FastAPI app setup, CORS, /health endpoint
├── api/routes.py        # All REST endpoints under /api prefix
├── agents/              # Multi-agent orchestration system
├── tools/               # Search and utility tools
├── core/
│   ├── config.py        # Pydantic settings (env vars)
│   └── llm_providers.py # LLM client factory (OpenAI/Anthropic/OpenRouter)
└── database/
    ├── base.py          # Abstract ChatStorage interface
    ├── sqlite.py        # SQLite implementation (default)
    └── postgres.py      # PostgreSQL implementation
```

### Frontend Structure

```
frontend/src/
├── App.tsx              # Router setup, global state
├── pages/
│   ├── ChatPage.tsx     # Main chat interface with SSE streaming
│   └── SettingsPage.tsx # Provider/model configuration, per-agent settings
├── components/
│   ├── Sidebar.tsx      # Conversation history sidebar
│   └── SearchableSelect.tsx # Model dropdown component
├── contexts/ChatContext.tsx # React Context for chat state
└── lib/
    ├── types.ts         # TypeScript interfaces
    └── streamManager.ts # SSE stream handling
```

### Key Data Flow

1. User sends message via `/api/chat` (POST)
2. Backend streams response via Server-Sent Events (SSE)
3. Progress events (`progress_event`) show real-time agent actions
4. Final response includes citations in Wikipedia-style format with superscript links
5. Conversation persisted to SQLite/PostgreSQL

### API Endpoints

Main endpoints in `api/routes.py`:
- `POST /api/chat` - Send message with SSE streaming response
- `GET/POST /api/settings/{session_id}` - User settings CRUD
- `GET /api/models/{provider}` - List available models for provider
- `GET /api/conversations` - List conversations
- `GET/DELETE /api/conversations/{id}` - Conversation operations
- `POST /api/search` - Direct search endpoint

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` - LLM provider keys
- `TAVILY_API_KEY`, `SERPAPI_API_KEY` - Search API keys
- `DB_TYPE` - `sqlite` (default) or `postgres`

Settings persist to `config/settings.json` and database.

## Key Patterns

- **Progress Callbacks**: Agents emit progress via callbacks for real-time UI updates
- **Async/Await**: All backend operations are async for concurrency
- **Provider Abstraction**: `get_llm_client()` in `llm_providers.py` returns appropriate client
- **Subagent Context**: `SubagentContext` dataclass passes state between agents
- **Stream Management**: `streamManager.ts` handles SSE parsing and event dispatch
