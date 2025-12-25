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
- **Quick Search** - Fast web search using Tavily API for current information
- **Deep Research** - Comprehensive multi-step research that:
  - Generates multiple sub-queries for thorough coverage
  - Searches in parallel for efficiency
  - Scrapes and reads full page content
  - Synthesizes information from multiple sources
- **Web Scraper** - Extract content from specific URLs

### Modern UI
- Real-time streaming responses with Server-Sent Events (SSE)
- Progress indicators showing research steps
- Searchable model dropdown with 100+ models
- Dark theme interface
- Persistent settings across sessions
- Deep Research toggle for switching between quick and comprehensive research modes

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
- Tavily API key for web search functionality

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

   # Required: For web search functionality
   TAVILY_API_KEY=tvly-...
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
| `OPENAI_API_KEY` | One of three | OpenAI API key |
| `ANTHROPIC_API_KEY` | One of three | Anthropic API key |
| `OPENROUTER_API_KEY` | One of three | OpenRouter API key |
| `TAVILY_API_KEY` | Yes | Tavily API key for web search |

### Settings Persistence

User settings are automatically saved to `config/settings.json` and persist across container restarts. Settings include:
- Selected provider and model
- Custom system prompt
- Deep research toggle state

## Architecture

```
ai-search-agent/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/            # REST API endpoints
│   │   ├── agents/         # Search agent with streaming
│   │   ├── core/           # Configuration, LLM providers
│   │   └── tools/          # Tavily, Deep Search, Web Scraper
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── lib/            # Types and utilities
│   │   └── App.tsx         # Main application
│   ├── Dockerfile
│   └── package.json
├── config/                 # Persistent configuration
│   └── settings.json       # User settings (auto-generated)
├── docker-compose.yml
└── .env                    # API keys (create from .env.example)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Health check and provider availability |
| `/api/models/{provider}` | GET | List available models for a provider |
| `/api/chat` | POST | Send message with streaming response |
| `/api/settings/{session_id}` | GET | Get saved settings |
| `/api/settings/{session_id}` | POST | Save settings |
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

### Quick Search vs Deep Research

- **Quick Search (default)**: Best for simple factual queries, news, and quick lookups. Uses Tavily search and responds faster.

- **Deep Research (toggle on)**: Best for complex topics requiring comprehensive coverage. Performs multiple searches, reads full articles, and synthesizes information. Takes longer but produces more thorough reports.

### Getting Best Results

1. Be specific in your queries
2. For research topics, enable Deep Research mode
3. The agent will automatically cite sources - check the References section for source links
4. Use follow-up questions to dive deeper into specific aspects

## Roadmap

- [ ] Conversation history persistence
- [ ] Export reports to PDF/Markdown
- [ ] Image search and embedding
- [ ] Custom tool plugins
- [ ] Multi-language support
- [ ] Rate limiting and usage tracking
- [ ] Authentication system

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

- [Tavily](https://tavily.com/) for the search API
- [OpenAI](https://openai.com/), [Anthropic](https://anthropic.com/), and [OpenRouter](https://openrouter.ai/) for LLM APIs
- The open-source community for the amazing tools and libraries

## Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/ai-search-agent/issues) page
2. Create a new issue with detailed information about your problem
3. Include logs from `docker logs ai-agent-backend` and `docker logs ai-agent-frontend`

---

**Note:** This project is not affiliated with OpenAI, Anthropic, or any other AI provider. Use responsibly and in accordance with each provider's terms of service.
