# AI Search Agent

> **Notice: This project is under active development.** Features may change, and some functionality might be incomplete or unstable. Contributions and feedback are welcome!

A powerful AI-powered research assistant with a modern web UI that can search the web, perform deep research, and generate comprehensive, well-cited reports in Wikipedia-style format.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-in%20development-yellow.svg)

## Features

### Multi-Provider LLM Support
- **OpenAI** - GPT-4o, GPT-4, GPT-3.5, o1, o3, and more
- **Anthropic** - Claude Sonnet, Claude Haiku, Claude Opus
- **OpenRouter** - Access to 100+ models from various providers

### Research Tools
- **Multiple Search Engines**:
  - **Tavily Search** - AI-optimized search engine for current information
  - **SerpAPI** - Google search results with answer boxes and knowledge graphs
- **Deep Research** - Comprehensive multi-step research that:
  - Generates multiple sub-queries for thorough coverage
  - Searches in parallel for efficiency
  - Scrapes and reads full page content
  - Synthesizes information from multiple sources
- **Web Scraper** - Extract content from specific URLs
- **Multi-Agent Orchestration (Beta)** - Advanced mode that:
  - Uses specialized subagents for planning, searching, and tool execution
  - Dynamically routes queries based on complexity
  - Synthesizes results from multiple subagents

### Modern UI
- Real-time streaming responses with Server-Sent Events (SSE)
- Progress indicators showing research steps
- Searchable model dropdown with 100+ models
- Dark theme interface
- Persistent conversation history with SQLite/PostgreSQL support
- Advanced settings:
  - Deep Research toggle for switching between quick and comprehensive research modes
  - Multi-Agent Orchestration mode for complex queries
  - Per-agent configuration (assign different models/providers to each subagent)
  - Custom system prompts for each agent
  - Max tokens control for response length
  - Timezone configuration

### Output Quality
- Wikipedia-style formal writing
- Superscript citations with clickable links
- Structured with headers and sections
- References section with all sources

## Screenshots

*Coming soon*

## Quick Start

### Prerequisites
- Docker and Docker Compose
- API keys for at least one LLM provider (OpenAI, Anthropic, or OpenRouter)
- At least one search API key (Tavily or SerpAPI recommended for web search functionality)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-search-agent.git
   cd ai-search-agent
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure API keys**

   Edit `.env` and add your API keys:
   ```env
   # Required: At least one LLM provider
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   OPENROUTER_API_KEY=sk-or-...

   # Recommended: At least one search API for web search functionality
   TAVILY_API_KEY=tvly-...        # AI-optimized search
   SERPAPI_API_KEY=your-key...    # Google search results
   ```

4. **Start the application**
   ```bash
   docker-compose up --build -d
   ```

5. **Access the UI**
   
   Open http://localhost:5173 in your browser

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | One required | OpenAI API key for GPT models |
| `ANTHROPIC_API_KEY` | One required | Anthropic API key for Claude models |
| `OPENROUTER_API_KEY` | One required | OpenRouter API key for 100+ models |
| `TAVILY_API_KEY` | Recommended | Tavily API key for AI-optimized web search |
| `SERPAPI_API_KEY` | Optional | SerpAPI key for Google search results |
| `DB_TYPE` | Optional | Database type: `sqlite` (default) or `postgres` |
| `POSTGRES_*` | If postgres | PostgreSQL connection settings |

### Settings Persistence

User settings are automatically saved to `config/settings.json` and persist across container restarts. Settings include:
- Selected provider and model
- Custom system prompt
- Deep research toggle state
- Multi-agent orchestration mode
- Per-agent configuration (models, providers, system prompts)
- Max tokens for response length
- Timezone preferences

Conversation history is stored in SQLite (default) or PostgreSQL database and persists across sessions.

## Architecture

```
ai-search-agent/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/            # REST API endpoints
│   │   ├── agents/         # Agent system
│   │   │   ├── search_agent.py         # Single-agent mode
│   │   │   ├── master_agent.py         # Multi-agent orchestrator
│   │   │   ├── planner_agent.py        # Research planning
│   │   │   ├── search_scraper_agent.py # Search execution
│   │   │   └── tool_executor_agent.py  # Tool execution
│   │   ├── core/           # Configuration, LLM providers
│   │   ├── tools/          # Search tools and utilities
│   │   │   ├── tavily_search.py        # Tavily API
│   │   │   ├── serpapi_search.py       # SerpAPI/Google
│   │   │   ├── deep_search.py          # Multi-query research
│   │   │   └── web_scraper.py          # URL scraping
│   │   └── storage/        # Database persistence
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/     # UI components (sidebar, markdown)
│   │   ├── contexts/       # React contexts (chat state)
│   │   ├── pages/          # Chat and Settings pages
│   │   ├── lib/            # Types and utilities
│   │   └── App.tsx         # Main application
│   ├── Dockerfile
│   └── package.json
├── config/                 # Persistent configuration
│   └── settings.json       # User settings (auto-generated)
├── data/                   # Database storage (auto-generated)
│   └── chat_history.db     # SQLite conversation history
├── docker-compose.yml
└── .env                    # API keys (create from .env.example)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Health check and provider availability |
| `/api/models/{provider}` | GET | List available models for a provider |
| `/api/chat` | POST | Send message with streaming response (SSE) |
| `/api/settings/{session_id}` | GET | Get saved settings |
| `/api/settings/{session_id}` | POST | Save settings |
| `/api/conversations` | GET | List all conversations |
| `/api/conversations/{id}` | GET | Get conversation details |
| `/api/conversations/{id}` | DELETE | Delete a conversation |
| `/api/conversations/{id}/messages` | GET | Get messages in a conversation |
| `/api/session/{session_id}/reset` | POST | Clear chat history |

## Development

### Running Locally (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Tech Stack

**Backend:**
- Python 3.12
- FastAPI
- OpenAI SDK
- Anthropic SDK
- Tavily Python
- BeautifulSoup4 + lxml

**Frontend:**
- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Markdown with rehype-raw

## Usage Tips

### Search Modes

- **Quick Search (default)**: Best for simple factual queries, news, and quick lookups. Faster responses using available search APIs.

- **Deep Research (toggle on)**: Best for complex topics requiring comprehensive coverage. Performs multiple searches, reads full articles, and synthesizes information. Takes longer but produces more thorough reports.

### Multi-Agent Mode (Beta)

Enable Multi-Agent Orchestration in settings for:
- **Complex queries** that benefit from planning before execution
- **Cost optimization** by assigning cheaper models to subagents
- **Performance tuning** by using different providers for different tasks

**How it works:**
1. **MasterAgent** analyzes your query and routes to specialized subagents
2. **PlannerAgent** creates research plans for complex topics
3. **SearchScraperAgent** executes searches and scrapes content
4. **ToolExecutorAgent** handles utilities like datetime queries

**Per-Agent Configuration:**
- Assign different models/providers to each agent (e.g., GPT-4 for planning, GPT-3.5 for search)
- Customize system prompts for each agent's specialty
- Optimize cost vs. quality tradeoffs

### Getting Best Results

1. Be specific in your queries
2. For research topics, enable Deep Research mode
3. For complex multi-step queries, try Multi-Agent mode
4. The agent will automatically cite sources - check the References section for source links
5. Use follow-up questions to dive deeper into specific aspects
6. Adjust max tokens in settings to control response length

## Roadmap

- [x] Conversation history persistence (SQLite/PostgreSQL)
- [x] Multi-agent orchestration system
- [x] Multiple search providers (Tavily, SerpAPI)
- [x] Per-agent configuration and optimization
- [ ] Export conversations to PDF/Markdown
- [ ] Image search and embedding in responses
- [ ] Custom tool plugins and extensions
- [ ] Multi-language support for UI and responses
- [ ] Rate limiting and usage tracking
- [ ] Authentication and user management
- [ ] Streaming for multi-agent progress
- [ ] Agent performance analytics

## Contributing

Contributions are welcome! This project is under active development, so please:

1. Check existing issues before creating new ones
2. Fork the repository
3. Create a feature branch (`git checkout -b feature/amazing-feature`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tavily](https://tavily.com/) for AI-optimized search API
- [SerpAPI](https://serpapi.com/) for Google search API
- [OpenAI](https://openai.com/), [Anthropic](https://anthropic.com/), and [OpenRouter](https://openrouter.ai/) for LLM APIs
- The open-source community for the amazing tools and libraries

## Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/ai-search-agent/issues) page
2. Create a new issue with detailed information about your problem
3. Include logs from `docker logs ai-agent-backend` and `docker logs ai-agent-frontend`

---

**Note:** This project is not affiliated with OpenAI, Anthropic, or any other AI provider. Use responsibly and in accordance with each provider's terms of service.
